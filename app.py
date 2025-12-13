import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 确保data目录存在
if not os.path.exists('data'):
    os.makedirs('data')

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
            'total_credits': total_credits,
            'total_debts': total_debts
        }), 400
    
    # 使用贪心算法匹配债权人和债务人
    transactions = []
    i, j = 0, 0
    
    while i < len(creditors) and j < len(debtors):
        creditor = creditors[i]
        debtor = debtors[j]
        
        if creditor['amount'] > debtor['amount']:
            # 债务人付清全部欠款，但债权人还未收完
            transactions.append({
                'from': debtor['name'],
                'to': creditor['name'],
                'amount': debtor['amount']
            })
            creditor['amount'] -= debtor['amount']
            j += 1
        elif creditor['amount'] < debtor['amount']:
            # 债权人收完全部款项，但债务人还有欠款
            transactions.append({
                'from': debtor['name'],
                'to': creditor['name'],
                'amount': creditor['amount']
            })
            debtor['amount'] -= creditor['amount']
            i += 1
        else:
            # 恰好相等
            transactions.append({
                'from': debtor['name'],
                'to': creditor['name'],
                'amount': creditor['amount']
            })
            i += 1
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
    result_files = [f for f in os.listdir('data') if f.startswith('result_') and f.endswith('.json')]
    
    # 计算每个玩家的总盈亏
    player_totals = {}
    
    for filename in result_files:
        file_path = os.path.join('data', filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
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
        except Exception as e:
            print(f"读取文件 {filename} 时出错: {e}")
    
    # 将字典转换为列表以便在模板中排序
    player_list = [{'name': name, 'total_profit': total} for name, total in player_totals.items()]
    
    # 按总盈亏排序（从高到低）
    player_list.sort(key=lambda x: x['total_profit'], reverse=True)
    
    return render_template('player_history.html', players=player_list)

@app.route('/player_history_detail/<player_name>')
def player_history_detail(player_name):
    """显示指定玩家的盈亏明细"""
    # 获取所有历史记录文件
    result_files = [f for f in os.listdir('data') if f.startswith('result_') and f.endswith('.json')]
    
    # 收集该玩家的所有历史记录
    player_details = []
    total_profit = 0
    
    for filename in result_files:
        file_path = os.path.join('data', filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
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
                        formatted_time = ''
                        if timestamp:
                            try:
                                # 解析时间戳 (格式: YYYYMMDD_HHMMSS)
                                dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                formatted_time = timestamp
                        
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
        except Exception as e:
            print(f"读取文件 {filename} 时出错: {e}")
    
    # 按时间倒序排序
    player_details.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return render_template('player_history_detail.html', 
                         player_name=player_name, 
                         player_details=player_details, 
                         total_profit=total_profit)

if __name__ == '__main__':
    # 明确绑定到所有地址，确保外部可访问
    app.run(host='0.0.0.0', port=5010, debug=False)