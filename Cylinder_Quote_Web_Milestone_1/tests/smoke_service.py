from pathlib import Path
from app.service import make_engine, calculate_payload

root = Path(__file__).resolve().parents[1]
engine = make_engine(root)
scenarios = [
    {"series":"H","bore":"2","rod_diameter":"1","mount":"MX0","stroke":"12","cushion":"NC","port_code":"N","seal_code":"","rod_style":1,"discount":"0"},
    {"series":"A","bore":"2","rod_diameter":"1","mount":"MX0","stroke":"8","cushion":"BE","port_code":"N","seal_code":"B","rod_style":1,"discount":"0.15","dre":True},
    {"series":"IH","bore":"25","rod_diameter":"12","mount":"ME3","stroke":"300","cushion":"RE","port_code":"S","seal_code":"V","rod_style":1,"discount":"0.05"},
]
for n,p in enumerate(scenarios,1):
    try:
        r=calculate_payload(engine,p)
        print(n, r['model_code'], r['quote_net_each'])
    except Exception as e:
        print(n, 'ERROR', e)
