import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

# 确保data目录存在
if not os.path.exists('data'):
    os.makedirs('data')

# 公共函数
def get_result_files():
    """获取所有历史记录文件"""
    return [f for f in os.listdir('data') if f.startswith('result_') and f.endswith('.json')]

def read_json_file(file_path, filename):
    """读取并解析JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"读取文件 {filename} 时出错: {e}")
        return None

def format_timestamp(timestamp):
    """格式化时间戳为易读形式"""
    if not timestamp:
        return ''
    try:
        # 解析时间戳 (格式: YYYYMMDD_HHMMSS)
        dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return timestamp

@app.route('/')
def index():
    return render_template('chips_calculator.html')

@app.route('/calculate_transactions', methods=['POST'])
def calculate_transactions():
    data = request.json
    initial_chips = data.get('initialChips', 200)
    players = data.get('players', [])
    
    # 计算每个玩家的盈亏
    creditors = []  # 赢家 (正数)
    debtors = []    # 输家 (负数)
    total_credits = 0  # 总盈利
    total_debts = 0    # 总亏损
    
    for player in players:
        diff = player['finalChips'] - initial_chips
        if diff > 0:
            creditors.append({'name': player['name'], 'amount': diff})
            total_credits += diff
        elif diff < 0:
            debtors.append({'name': player['name'], 'amount': -diff})
            total_debts += -diff
    
    # 验证总盈利是否等于总亏损
    if abs(total_credits - total_debts) > 0.01:  # 允许微小的浮点数误差
        return jsonify({
            'error': '数据错误',
            'message': '玩家总亏损与总盈利不相等，请检查输入的筹码数量',
            'details': {
                'total_credits': total_credits,
                'total_debts': total_debts
            }
        }), 400
    
    # 使用贪心算法匹配债权人和债务人
    transactions = []
    i, j = 0, 0
    
    while i < len(creditors) and j < len(debtors):
        creditor = creditors[i]
        debtor = debtors[j]
        transfer_amount = min(creditor['amount'], debtor['amount'])
        
        # 添加转账记录
        transactions.append({
            'from': debtor['name'],
            'to': creditor['name'],
            'amount': transfer_amount
        })
        
        # 更新剩余金额
        creditor['amount'] -= transfer_amount
        debtor['amount'] -= transfer_amount
        
        # 移动指针
        if creditor['amount'] == 0:
            i += 1
        if debtor['amount'] == 0:
            j += 1
    
    # 保存计算结果到data目录
    save_calculation_result(initial_chips, players, transactions)
    
    return jsonify({'transactions': transactions})


@app.route('/get_users')
def get_users():
    """获取所有可用用户列表"""
    users_file = 'data/users.txt'
    users = []
    
    if os.path.exists(users_file):
        with open(users_file, 'r', encoding='utf-8') as f:
            users = [line.strip() for line in f.readlines() if line.strip()]
    
    return jsonify({'users': users})

def save_calculation_result(initial_chips, players, transactions):
    """保存计算结果到data目录"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"data/result_{timestamp}.json"
    
    result_data = {
        "timestamp": timestamp,
        "initial_chips": initial_chips,
        "players": players,
        "transactions": transactions
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

@app.route('/player_history')
def player_history():
    """显示所有玩家的历史总盈亏"""
    # 获取所有历史记录文件
    result_files = get_result_files()
    
    # 计算每个玩家的总盈亏
    player_totals = {}
    
    for filename in result_files:
        file_path = os.path.join('data', filename)
        data = read_json_file(file_path, filename)
        if data is None:
            continue
            
        initial_chips = data.get('initial_chips', 200)
        players = data.get('players', [])
        
        for player in players:
            name = player['name']
            final_chips = player['finalChips']
            # 计算该玩家在本次记录中的盈亏
            profit = final_chips - initial_chips
            
            # 更新总盈亏
            if name in player_totals:
                player_totals[name] += profit
            else:
                player_totals[name] = profit
    
    # 将字典转换为列表以便在模板中排序
    player_list = [{'name': name, 'total_profit': total} for name, total in player_totals.items()]
    
    # 按总盈亏排序（从高到低）
    player_list.sort(key=lambda x: x['total_profit'], reverse=True)
    
    return render_template('player_history.html', players=player_list)

@app.route('/player_history_detail/<player_name>')
def player_history_detail(player_name):
    """显示指定玩家的盈亏明细"""
    # 获取所有历史记录文件
    result_files = get_result_files()
    
    # 收集该玩家的所有历史记录
    player_details = []
    total_profit = 0
    
    for filename in result_files:
        file_path = os.path.join('data', filename)
        data = read_json_file(file_path, filename)
        if data is None:
            continue
            
        timestamp = data.get('timestamp', '')
        initial_chips = data.get('initial_chips', 200)
        players = data.get('players', [])
        transactions = data.get('transactions', [])
        
        # 查找当前玩家的记录
        for player in players:
            if player['name'] == player_name:
                final_chips = player['finalChips']
                profit = final_chips - initial_chips
                total_profit += profit
                
                # 转换时间格式为易读形式
                formatted_time = format_timestamp(timestamp)
                
                # 添加明细记录
                detail = {
                    'timestamp': formatted_time,
                    'initial_chips': initial_chips,
                    'final_chips': final_chips,
                    'profit': profit
                }
                
                # 特殊处理：只有两个玩家的情况
                if len(players) == 2:
                    for transaction in transactions:
                        if transaction['from'] == player_name:
                            # 当前玩家是转账方（亏损）
                            detail['transfer_info'] = f"转账给 {transaction['to']} {transaction['amount']} 筹码"
                            detail['is_transfer_out'] = True
                            break
                        elif transaction['to'] == player_name:
                            # 当前玩家是收款方（盈利）
                            detail['transfer_info'] = f"从 {transaction['from']} 收到 {transaction['amount']} 筹码"
                            detail['is_transfer_in'] = True
                            break
                
                player_details.append(detail)
    
    # 按时间倒序排序
    player_details.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return render_template('player_history_detail.html', 
                         player_name=player_name, 
                         player_details=player_details, 
                         total_profit=total_profit)

@app.route('/transfer')
def transfer():
    """显示两个玩家之间的转账记录界面"""
    return render_template('transfer.html')

@app.route('/save_transfer', methods=['POST'])
def save_transfer():
    """保存两个玩家之间的转账记录"""
    data = request.json
    sender = data.get('from_player')
    receiver = data.get('to_player')
    amount_str = data.get('amount')
    
    # 验证输入
    if not sender or not receiver or not amount_str:
        return jsonify({'error': '请填写完整信息'})
    
    if sender == receiver:
        return jsonify({'error': '不能给自己转账'})
    
    try:
        amount = int(amount_str)
        if amount <= 0:
            return jsonify({'error': '转账金额必须为正数'})
    except ValueError:
        return jsonify({'error': '转账金额必须为数字'})
    
    # 创建转账记录数据
    initial_chips = 200  # 默认初始筹码
    
    # 根据转账信息创建玩家数据
    sender_data = {"name": sender, "finalChips": initial_chips - amount}
    receiver_data = {"name": receiver, "finalChips": initial_chips + amount}
    
    # 创建转账记录
    transaction = {"from": sender, "to": receiver, "amount": amount}
    
    # 保存计算结果到data目录
    save_calculation_result(initial_chips, [sender_data, receiver_data], [transaction])
    logging.info(f"转账记录已保存: {sender} 转 {amount} 筹码给 {receiver}")
    
    return jsonify({'success': '转账记录已保存'})

if __name__ == '__main__':
    # 明确绑定到所有地址，确保外部可访问
    app.run(host='0.0.0.0', port=5010, debug=False)