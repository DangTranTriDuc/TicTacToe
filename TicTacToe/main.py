from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List
import uvicorn

app = FastAPI()

players: List[WebSocket] = []
symbols = ['X', 'O']
board = [""] * 9
moves = {"X": [], "O": []}
current_turn = "X"

# Các tổ hợp thắng
win_combinations = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8],  # hàng ngang
    [0, 3, 6], [1, 4, 7], [2, 5, 8],  # hàng dọc
    [0, 4, 8], [2, 4, 6]  # chéo
]


@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


def get_symbol(ws: WebSocket):
    idx = players.index(ws)
    return symbols[idx]


def check_winner():
    for combo in win_combinations:
        a, b, c = combo
        if board[a] and board[a] == board[b] == board[c]:
            return board[a], combo
    return None, None


async def broadcast_board():
    for p in players:
        await p.send_json({"type": "board", "board": board})


async def broadcast_winner(symbol, win_cells):
    for p in players:
        await p.send_json({
            "type": "winner",
            "symbol": symbol,
            "win_cells": win_cells
        })


def reset_game():
    global board, moves, current_turn
    board = [""] * 9
    moves = {"X": [], "O": []}
    current_turn = "X"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global current_turn
    await websocket.accept()

    if len(players) >= 2:
        await websocket.close()
        return

    players.append(websocket)
    player_symbol = symbols[players.index(websocket)]
    await websocket.send_json({"type": "assign", "symbol": player_symbol})
    await broadcast_board()

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "move":
                index = data["index"]
                if board[index] != "" or player_symbol != current_turn:
                    continue

                if len(moves[player_symbol]) >= 3:
                    old_index = moves[player_symbol].pop(0)
                    board[old_index] = ""

                board[index] = player_symbol
                moves[player_symbol].append(index)

                winner, win_cells = check_winner()
                if winner:
                    await broadcast_board()
                    await broadcast_winner(winner, win_cells)
                else:
                    current_turn = "O" if current_turn == "X" else "X"
                    await broadcast_board()

            elif data["type"] == "timeout":
                loser = player_symbol
                winner = "O" if loser == "X" else "X"
                await broadcast_winner(winner, [])
                reset_game()
                await broadcast_board()

            elif data["type"] == "reset":  # ✅ Xử lý reset từ client
                reset_game()
                await broadcast_board()

    except WebSocketDisconnect:
        if websocket in players:
            players.remove(websocket)
        reset_game()
