#!/usr/bin/env python3
"""
Test de conexión y orden paper con IB Gateway (puerto 4002).
"""
from ib_insync import IB, Stock, LimitOrder

ib = IB()
try:
    ib.connect('127.0.0.1', 7497, clientId=1, readonly=False, timeout=10)
    print(f"✅ Conectado — cuenta: {ib.wrapper.accounts}")

    account = ib.wrapper.accounts[0]
    nav = ib.accountSummary(account)
    for item in nav:
        if item.tag == 'NetLiquidation':
            print(f"✅ Valor portfolio paper: ${float(item.value):,.0f}")
            break

    # Orden límite de prueba en AAPL (precio muy bajo para que no se ejecute)
    contract = Stock('AAPL', 'SMART', 'USD')
    ib.qualifyContracts(contract)

    order = LimitOrder('BUY', totalQuantity=1, lmtPrice=1.00)
    order.account = account
    trade = ib.placeOrder(contract, order)
    ib.sleep(2)

    print(f"✅ Orden de prueba colocada — status: {trade.orderStatus.status}")

    # Cancelar la orden de prueba
    ib.cancelOrder(order)
    ib.sleep(1)
    print("✅ Orden cancelada — sistema listo para operar")

    ib.disconnect()

except Exception as e:
    print(f"❌ Error: {e}")
