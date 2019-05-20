import boto3
from twilio.rest import Client

# Account IDs and keys needed to access AWS and Twilio
aws_access_key_id = ''
aws_secret_access_key = ''
account_sid = ''
auth_token = ''
twilio_number = ''


# Connect to AWS DynamoDB and Twilio
dynamodb = boto3.resource('dynamodb',
                          aws_access_key_id=aws_access_key_id,
                          aws_secret_access_key=aws_secret_access_key,
                          region_name='us-east-1')
client = Client(account_sid, auth_token)


# Set up an empty 3x3 tic tac toe board
empty = '  '
horizontal = ' ' + '  _' * 3
top = {'t1': '1', 't2': '2', 't3': '3'}
empty_board = {
    'a': {'a1': empty, 'a2': empty, 'a3': empty},
    'b': {'b1': empty, 'b2': empty, 'b3': empty},
    'c': {'c1': empty, 'c2': empty, 'c3': empty},
}


def generate_row(row):
    return '|' + '|'.join(row[item] for item in sorted(row.keys())) + '|'


def draw_board(board):
    """
    Given the current state of the board, render the dictionary as a simple text version of a tic tac toe board
    :param board: dictionary containing the current game state
    :return: String representation of the board
    """
    rendered_board = f'\n{empty}'+''.join((generate_row(top)))+'\n'
    for label, row in board.items():
        rendered_board += f'\n{label}'.join((horizontal, generate_row(row)))+'\n'
    rendered_board += horizontal

    return rendered_board


def swap_player_turn(turn):
    if turn == 1:
        return 2
    else:
        return 1


def validate_move(move, turn, board):
    """
    Determine if the next move is valid for the current player
    :param move:
    :param turn:
    :param board:
    :return: boolean flag for if the move is valid as well as the current gamestate dictionary
    """
    if turn == 1:
        piece = 'X'
    else:
        piece = 'O'

    try:
        if board[move[:-1]][move] not in ('X', 'O'):
            board[move[:-1]][move] = piece
            return True, board
        else:
            return False, board
    except KeyError:
        return False, board


def _is_win_line(line):
    print(line)
    if len(line) == 1:
        if line == set('X') or line == set('O'):
            return True
    return False


def validate_win(board):
    """
    Loop through the board and determine if any win conditions are met
    :param board: dictionary of current game state
    :return: boolean flag for if the game has been won
    """
    columns = {1: [], 2: [], 3: []}

    for letter in ('a', 'b', 'c'):
        for _ in range(1, 4):
            columns[_].append(board[letter][f'{letter}{_}'])
        if _is_win_line(set(board[letter].values())):
            return True

    for first, second in ((1, 3), (3, 1)):
        if _is_win_line({board['a'][f'a{first}'], board['b']['b2'], board['c'][f'c{second}']}):
            return True

    return False


def clean_up_number(phone_number):
    return phone_number.replace('%2B1', '')


def update_table(table, game_id, board, turn, turn_count, game_over, confirmed_game):
    """
    Update an existing game state
    :param table: dynamodb table
    :param game_id: unique game ID
    :param board: current board state
    :param turn: player turn ID (1 or 2)
    :param turn_count: how many turns the game has been running
    :param game_over: boolean flag to show the game has been completed
    :param confirmed_game: boolean flag to signify that player 2 has accepted game challenge
    """
    table.update_item(
        Key={
            'game_id': game_id
        },
        UpdateExpression="set board=:b, player_turn=:t, turn_count=:c, game_over=:g, confirmed_game=:f",
        ExpressionAttributeValues={
            ':b': board,
            ':t': turn,
            ':c': turn_count,
            ':g': game_over,
            ':f': confirmed_game

        },
        ReturnValues="UPDATED_NEW"
    )


def delete_table_item(table, game_id):
    """
    Delete currently existing game
    :param table: dynamodb table
    :param game_id: unique game ID
    """
    table.delete_item(
        Key={
            'game_id': game_id
        }
    )


def send_message(to_number, body):
    client.messages.create(
        to=f'+1{to_number}',
        from_=twilio_number,
        body=body
    )


def lambda_handler(event):
    new_game = False

    message = event

    table = dynamodb.Table('tic_tac_toe')

    from_player = clean_up_number(message['From'])
    target_player = message['Body'].split('+')[0]
    game_id = str(int(from_player) + int(target_player))

    if 'challenge' in message['Body'].lower():
        new_game = True
    elif 'confirm' in message['Body'].lower():
        send_message(target_player, f'Your turn against {from_player}\n {draw_board(empty_board)}')
    elif 'a' in message['Body'].lower() or 'b' in message['Body'].lower() or 'c' in message['Body'].lower():
        pass
    elif 'end' in message['Body'].lower():
        update_table(table, game_id, empty_board, 1, 0, False, False)
        send_message(from_player, f"ending game based on player {from_player}'s request")
        send_message(target_player, f"ending game based on player {from_player}'s request")
        delete_table_item(table, game_id)
        return None
    else:
        send_message(from_player, 'Invalid input, try again')

    details = table.get_item(
        Key={
            'game_id': game_id
        }
    )

    try:
        game_data = details['Item']
    except KeyError:
        if new_game:
            board = empty_board
            player_1 = from_player
            player_2 = target_player
            turn = 1
            turn_count = 0
            game_over = False
            confirmed_game = False

            table.put_item(
                Item={
                    'game_id': game_id,
                    'player_1': player_1,
                    'player_2': player_2,
                    'player_turn': turn,
                    'turn_count': turn_count,
                    'game_over': game_over,
                    'board': board,
                    'confirmed_game': confirmed_game
                }
            )
            send_message(from_player, f'Challenging {player_2}, sending them a confirmation')
            send_message(target_player, f'{from_player} challenges you to tic tac toe, type "{from_player} confirmed" '
                                        f'to accept or nothing to decline')
            return None
        else:
            send_message(from_player, 'Not a new game')
            return None
    else:
        board = game_data['board']
        player_1 = game_data['player_1']
        player_2 = game_data['player_2']
        turn = game_data['player_turn']
        turn_count = game_data['turn_count']
        confirmed_game = game_data['confirmed_game']
        game_over = game_data['game_over']

    # Which player is this
    if from_player == player_1 and turn == 1:
        pass
    elif from_player == player_2 and turn in (1, 2):
        pass
    else:
        send_message(from_player, f"It is not currently your turn")
        return None

    move = message['Body'].lower().split("+")[1]

    valid_move, board = validate_move(move, turn, board)
    if not valid_move:
        send_message(from_player, f'{move} is invalid, try again you dingus')
        return None

    if validate_win(board):
        game_over = True
        update_table(table, game_id, board, turn, turn_count, game_over, confirmed_game)
        send_message(from_player, f'You win!')
        send_message(target_player, f'Player {turn} wins!')
        delete_table_item(table, game_id)
        return None

    turn = swap_player_turn(turn)
    turn_count += 1

    if turn_count == 9:
        game_over = True
        response = "Game over, no more moves left"
        update_table(table, game_id, board, turn, turn_count, game_over, confirmed_game)
        send_message(from_player, response)
        send_message(target_player, response)
        delete_table_item(table, game_id)
        return None

    update_table(table, game_id, board, turn, turn_count, game_over, confirmed_game)
    send_message(target_player, f'Your turn against {from_player}\n {draw_board(board)}')
    return None
