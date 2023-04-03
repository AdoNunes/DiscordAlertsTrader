import place_order as pord


Session = pord.get_TDsession()


df_pos, df_ordr = pord.get_positions_orders(Session)


order = {"symbol": "ASO", 
         "uQty":1,
         "price":2,
         'strike':None,
         "price": 0.5,
         "PTs": [1,2,3],
         "PTs_Qty":[1,1,1],
         "SL": 0.1,
         "SL_stop": 0.2
         }
new_order_bto_lim = pord.make_BTO_lim_order(**order)

order_response, order_id =  pord.send_order(new_order_bto_lim, Session)
new_order=  pord.make_Lim_SL_order(**order)
new_order =  pord.make_STC_lim(**order)


resp = Session.get_quotes(instruments=[order['symbol']])
if resp[order['symbol']].get('description' ) == 'Symbol not found':
    print (f"{order['symbol']} not found during price quote")
else:
    quote = resp[order['symbol']]['lastPrice']
    print (f"{order['symbol']} quote: {quote}")

