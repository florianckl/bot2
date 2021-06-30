import json
import numpy
import talib
import websocket
from binance.client import Client
from binance.enums import *
import csv
import time
import config

SOCKET = "wss://stream.binance.com:9443/ws/btceur@kline_1h"
TRADE_SYMBOL = 'BTCEUR'
TRADE_QUANTITY = 0.0036

closes = []
maxprix = 0
minprix = 1000000
ordre_achat = []

nbAchat = 0
nbVente = 0
ordre_vente = []

client = Client(config.API_KEY, config.API_SECRET)


def vendre(prixdumarche):
    global maxprix, ordre_achat
    if float(ordre_achat[-1]["fills"][0]["price"]) * 1.01 <= maxprix < float(
            ordre_achat[-1]["fills"][0]["price"]) * 1.02:
        if float(maxprix) - float(prixdumarche) >= 0.5 * (float(maxprix) - float(ordre_achat[-1]["fills"][0]["price"])):
            print("50% pourcent")
            return True

    if float(ordre_achat[-1]["fills"][0]["price"]) * 1.02 <= maxprix:
        if float(maxprix) - float(prixdumarche) >= 0.25 * (
                float(maxprix) - float(ordre_achat[-1]["fills"][0]["price"])):
            print("25% pourcent")
            return True

    if float(ordre_achat[-1]["fills"][0]["price"]) * 0.99 > float(prixdumarche):
        print("1% pourcent perte")
        return True
    return False


def acheter(prixdumarche):
    global minprix, ordre_vente
    if float(ordre_vente[-1]["fills"][0]["price"]) * 0.99 > minprix >= float(
            ordre_vente[-1]["fills"][0]["price"]) * 0.98:
        if float(prixdumarche) - float(minprix) >= 0.5 * (float(ordre_vente[-1]["fills"][0]["price"]) - float(minprix)):
            print("50% pourcent")
            return True

    if float(ordre_vente[-1]["fills"][0]["price"]) * 0.98 > minprix:
        if float(prixdumarche) - float(minprix) >= 0.25 * (
                float(ordre_vente[-1]["fills"][0]["price"]) - float(minprix)):
            print("25% pourcent")
            return True

    if float(ordre_vente[-1]["fills"][0]["price"]) * 1.01 < float(prixdumarche):
        print("1% pourcent perte")
        return True
    return False


def order_buy(quantity, symbol, order_type=ORDER_TYPE_MARKET):
    global ordre_achat
    try:
        print("sending order")
        order = client.create_order(symbol=symbol, side=SIDE_BUY, type=order_type,
                                    newOrderRespType=ORDER_RESP_TYPE_FULL, quantity=quantity)
        ordre_achat.append(order)
        print(order)

    except Exception as e:
        print("an exception occured - {}".format(e))
        return False
    return True


def order_sell(quantity, symbol, order_type=ORDER_TYPE_MARKET):
    global ordre_achat
    try:
        print("sending order")
        order = client.create_order(symbol=symbol, side=SIDE_SELL, type=order_type,
                                    newOrderRespType=ORDER_RESP_TYPE_FULL, quantity=quantity)
        print(order)
        with open('order.csv', 'a') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(['sell', float(order["fills"][0]["price"]) - float(
                ordre_achat.pop()["fills"][0]["price"])])

    except Exception as e:
        print("an exception occured - {}".format(e))
        return False
    return True


def order_buy_short(quantity, symbol, order_type=ORDER_TYPE_MARKET):
    global ordre_vente
    try:
        print("sending order")
        order = client.create_margin_order(symbol=symbol, side=SIDE_BUY, type=order_type, isIsolated="TRUE",
                                           newOrderRespType=ORDER_RESP_TYPE_FULL, quantity=quantity)
        print(order)
        with open('order.csv', 'a') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(['buy_short', float(ordre_vente.pop()["fills"][0]["price"] - float(
                order["fills"][0]["price"]))])

    except Exception as e:
        print("an exception occured - {}".format(e))
        return False
    return True


def order_sell_short(quantity, symbol, order_type=ORDER_TYPE_MARKET):
    global ordre_vente
    try:
        print("sending order")
        order = client.create_margin_order(symbol=symbol, side=SIDE_SELL, type=order_type, isIsolated="TRUE",
                                           newOrderRespType=ORDER_RESP_TYPE_FULL, quantity=quantity)
        ordre_vente.append(order)
        print(order)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False
    return True


def on_open():
    global closes
    print('opened connection')
    list = client.get_historical_klines(symbol=TRADE_SYMBOL, interval=Client.KLINE_INTERVAL_1HOUR,
                                          start_str="30 hours ago UTC+1")
    for elem in list:
        closes.append(float(elem[4]))


def on_close():
    print("Probleme de connexion")
    time.sleep(15)
    websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message).run_forever()
    print('closed connection')


def on_message(message):
    global closes, nbAchat, nbVente, maxprix, minprix

    json_message = json.loads(message)
    candle = json_message['k']
    is_candle_closed = candle['x']
    close = candle['c']

    if is_candle_closed:
        closes.append(float(close))
        np_closes = numpy.array(closes)
        macd, macdsignal, macdhist = talib.MACD(np_closes, fastperiod=12, slowperiod=26, signalperiod=9)

        if macdhist[-1] > 0 and macdhist[-2] < 0:
            nbAchat = 0
            maxprix = 0

        if macdhist[-1] < 0 and macdhist[-2] > 0:
            nbVente = 0
            minprix = 1000000

        if macdhist[-1] > 0:
            if maxprix < float(close):
                maxprix = float(close)

            if macd > 15 and nbAchat == 0:
                order_succeeded = order_buy(TRADE_QUANTITY, TRADE_SYMBOL)
                if order_succeeded:
                    nbAchat = nbAchat + 1

            if nbAchat > 0 and vendre(float(close)) or macdhist[-2] > 0 and macdhist[-1] < 0:
                order_succeeded = order_sell(TRADE_QUANTITY, TRADE_SYMBOL)
                if order_succeeded:
                    nbAchat = nbAchat - 2

        if macdhist[-1] < 0:
            if minprix > float(close):
                minprix = float(close)

            if macd < -15 and nbVente == 0:
                order_succeeded = order_sell_short(TRADE_QUANTITY, TRADE_SYMBOL)
                if order_succeeded:
                    nbVente = nbVente + 1

            if nbVente > 0 and acheter(float(close)) or macdhist[-2] < 0 and macdhist[-1] > 0:
                order_succeeded = order_buy_short(TRADE_QUANTITY, TRADE_SYMBOL)
                if order_succeeded:
                    nbVente = nbVente - 2


websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message).run_forever()
