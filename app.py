  
# -*- coding: utf-8 -*-
import os
import json
import base64
import datetime
from flask.helpers import url_for
import requests
import pathlib
import math
import pandas as pd
import numpy as np
import flask
import dash
import dash_core_components as dcc
import dash_html_components as html
import chart_studio.plotly as py
import plotly.graph_objs as go
import alpaca_trade_api as tradeapi
from dash.dependencies import Input, Output, State
from plotly import tools
from dotenv import load_dotenv
load_dotenv()
import pyodbc

app = dash.Dash(
    __name__, meta_tags=[{"name": "viewport", "content": "width=device-width"}],suppress_callback_exceptions=True,
    url_base_pathname='/Dashboard/'
)

app.title = "Trading Viewer"

server = app.server
idx =pd.IndexSlice
PATH = pathlib.Path(__file__).parent
DATA_PATH = PATH.joinpath("data").resolve()

# Currency pairs
currencies = ["EURUSD", "USDCHF", "USDJPY", "GBPUSD"]

currencies = ['AAPL','CVX','FB','TSLA','XOM','A','M']

conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER='+os.environ.get('server')+ \
            ';DATABASE='+os.environ.get('database')+ \
                ';UID='+os.environ.get('dbusername')+ \
                    ';PWD='+ os.environ.get('dbpassword')
cnxn = pyodbc.connect(conn_str)       
cursor = cnxn.cursor()
cursor.execute("Select Top 10 Symbol, Predicted_Inc From Tickers Where Model_Accuracy > 0.7 Order By Predicted_Inc Desc")
predictions = pd.DataFrame([list(ele) for ele in cursor],columns=['Ticker','Prediction'])
currencies = predictions['Ticker'].tolist()

#Initialize Brokerage API conncection
api = tradeapi.REST(
        os.environ.get('AlpacaKey'),
        os.environ.get('AlpacaSecret'),
        'https://paper-api.alpaca.markets', api_version='v2')
        
#Initialize stock data api parameters
iex = 'https://sandbox.iexapis.com/stable'
token=os.environ.get('IEXTestKey')
params={'token': token,\
                            'symbols': ','.join(currencies), \
                            'types':'chart', \
                            'range':'1d', \
                            'chartLast': 2, \
                            'chartIEXOnly':'true'
                            }

def update_row_data():
    mindata = dict()
    resp=requests.get(iex+'/stock/market/batch',params=params)
    d=resp.json()
    df = pd.concat([pd.DataFrame(v) for k,v in d.items()], keys=d)
    df=df['chart'].apply(pd.Series)
    df['Symbol']=df.index.get_level_values(0).tolist()# Add Symbol to dataframe
    df['Symbol']=df['Symbol']
    df.rename(columns={'close':'ask','open':'bid'}, inplace=True)
    df['Date']=pd.to_datetime(df['date']+' '+df['minute'].astype(str))

    mindata = dict()
    for t in currencies:
        r = df.loc[idx[t,:]]
        r['Change'] = (r.iloc[-1]['ask']-r.iloc[0]['ask'])/r.iloc[0]['ask']*100
        mindata.update({t:r})
    return mindata
currency_pair_data=update_row_data()

# https://iexcloud.io/docs/api/#historical-prices
def getchartdata(tkr,chartdays):
    chartparams={'token': token,'chartCloseOnly':'false'}
    uri=iex+'/stock/{}/chart/{}'.format(tkr,chartdays)
    return  pd.DataFrame(requests.get(uri,params=chartparams).json())

# API Requests for news div
news_requests = requests.get(
    "https://newsapi.org/v2/top-headlines?sources=bloomberg&apiKey=da8e2e705b914f9f86ed2e9692e66012"
)

# API Call to update news
def update_news():
    json_data = news_requests.json()["articles"]
    df = pd.DataFrame(json_data)
    df = pd.DataFrame(df[["title", "url"]])
    max_rows = 10
    return html.Div(
        children=[
            html.P(className="p-news", children="Headlines"),
            html.P(
                className="p-news float-right",
                children="Last update : "
                + datetime.datetime.now().strftime("%H:%M:%S"),
            ),
            html.Table(
                className="table-news",
                children=[
                    html.Tr(
                        children=[
                            html.Td(
                                children=[
                                    html.A(
                                        className="td-link",
                                        children=df.iloc[i]["title"],
                                        href=df.iloc[i]["url"],
                                        target="_blank",
                                    )
                                ]
                            )
                        ]
                    )
                    for i in range(min(len(df), max_rows))
                ],
            ),
        ]
    )


# Returns dataset for currency pair with nearest datetime to current time
def first_ask_bid(currency_pair):
    df_row = currency_pair_data[currency_pair]
    int_index = currency_pair_data[currency_pair].index.tolist()[-1]
    return (df_row.iloc[int_index])  # returns dataset row and index of row


# Creates HTML Bid and Ask (Buy/Sell buttons)
def get_row(data):
    index = data.name
    current_row = data
    return html.Div(
        children=[
            # Summary
            html.Div(
                id=current_row['Symbol'] + "summary",
                className="row summary",
                n_clicks=0,
                children=[
                    html.Div(
                        id=current_row['Symbol'] + "row",
                        className="row",
                        children=[
                            html.P(
                                current_row['Symbol'],  # currency pair name
                                id=current_row['Symbol'],
                                className="three-col",
                            ),
                            html.P(
                                current_row['bid'].round(5),  # Bid value
                                id=current_row['Symbol'] + "bid",
                                className="three-col",
                            ),
                            html.P(
                                current_row['Change'].round(5),  # Ask value
                                id=current_row['Symbol'] + "ask",
                                className="three-col",
                            ),
                            html.Div(
                                current_row['Date'],
                                id=current_row['Symbol']
                                + "lastupdate",  # we save index of row in hidden div
                                style={"display": "none"},
                            ),
                        ],
                    )
                ],
            ),
            # Contents
            html.Div(
                id=current_row['Symbol'] + "contents",
                className="row details",
                children=[
                    # Button for buy/sell modal
                    # html.Div(
                    #     className="button-buy-sell-chart",
                    #     children=[
                    #         html.Button(
                    #             id=current_row['Symbol'] + "Buy",
                    #             children="Buy/Sell",
                    #             n_clicks=0,
                    #         )
                    #     ],
                    # ),
                    # Button to display currency pair chart
                    html.Div(
                        className="button-buy-sell-chart",
                        children=[
                            html.Button(
                                id=current_row['Symbol'] + "Button_chart",
                                children="Chart",
                                n_clicks=1
                                if any(current_row['Symbol']==elem for elem in currencies[:2])
                                else 0,
                            )
                        ],
                    ),
                ],
            ),
        ]
    )


# color of Bid & Ask rates
def get_color(a, b):
    if a == b:
        return "white"
    elif a > b:
        return "#45df7e"
    else:
        return "#da5657"


# Replace ask_bid row for currency pair with colored values
def replace_row(currency_pair, index, bid, ask):
    index = currency_pair_data[currency_pair].index.tolist()[-1]  # index of new data row
    new_row = (
        currency_pair_data[currency_pair].iloc[-1]
        if index != len(currency_pair_data[currency_pair])
        else first_ask_bid(currency_pair)
    )  # if not the end of the dataset we retrieve next dataset row

    return [
        html.P(
            currency_pair, id=currency_pair, className="three-col"  # currency pair name
        ),
        html.P(
            new_row[1].round(5),  # Bid value
            id=new_row[0] + "bid",
            className="three-col",
            style={"color": get_color(new_row[1], bid)},
        ),
        html.P(
            new_row[2].round(5),  # Ask value
            className="three-col",
            id=new_row[0] + "ask",
            style={"color": get_color(new_row[2], ask)},
        ),
        html.Div(
            index, id=currency_pair + "index", style={"display": "none"}
        ),  # save index in hidden div
    ]


# Display big numbers in readable format
def human_format(num):
    try:
        num = float(num)
        # If value is 0
        if num == 0:
            return 0
        # Else value is a number
        if num < 1000000:
            return num
        magnitude = int(math.log(num, 1000))
        mantissa = str(int(num / (1000 ** magnitude)))
        return mantissa + ["", "K", "M", "G", "T", "P"][magnitude]
    except:
        return num


# Returns Top cell bar for header area
def get_top_bar_cell(cellTitle, cellValue):
    return html.Div(
        className="two-col",
        children=[
            html.P(className="p-top-bar", children=cellTitle),
            html.P(id=cellTitle, className="display-none", children=cellValue),
            html.P(children=human_format(cellValue)),
        ],
    )


# Returns HTML Top Bar for app layout
def get_top_bar():
    accountinfo= api.get_account()
    positions= api.list_positions()
    open_pl = 0
    balance = float(accountinfo.portfolio_value)
    free_margin = float(accountinfo.buying_power)-float(accountinfo.non_marginable_buying_power)
    margin = float(accountinfo.buying_power)-float(accountinfo.non_marginable_buying_power)
    investments=float(accountinfo.long_market_value)
    cash=float(accountinfo.cash)
    for order in positions:
        open_pl += float(order.unrealized_pl)
        # balance += float(order["profit"])

    equity = float(accountinfo.equity)
    free_margin = equity - margin
    m_level = "%" if margin == 0 else "%2.F" % ((equity / margin) * 100) + "%"
    equity = "%.2F" % equity
    balance = "%.2F" % balance
    open_pl = "%.2F" % open_pl
    fm = "%.2F" % free_margin
    margin = "%2.F" % margin
    return [
        get_top_bar_cell("Balance", balance),
        get_top_bar_cell("Investments", investments),
        get_top_bar_cell("Margin", margin),
        get_top_bar_cell("Cash", cash),
        get_top_bar_cell("Margin Level", m_level),
        get_top_bar_cell("Open P/L", open_pl),
    ]


####### STUDIES TRACES ######

# Moving average
def moving_average_trace(df, fig):
    df2 = df.rolling(window=5).mean()
    trace = go.Scatter(
        x=df2.index, y=df2["close"], mode="lines", showlegend=False, name="MA"
    )
    fig.append_trace(trace, 1, 1)  # plot in first row
    return fig


# Exponential moving average
def e_moving_average_trace(df, fig):
    df2 = df.rolling(window=20).mean()
    trace = go.Scatter(
        x=df2.index, y=df2["close"], mode="lines", showlegend=False, name="EMA"
    )
    fig.append_trace(trace, 1, 1)  # plot in first row
    return fig


# Bollinger Bands
def bollinger_trace(df, fig, window_size=10, num_of_std=5):
    price = df["close"]
    rolling_mean = price.rolling(window=window_size).mean()
    rolling_std = price.rolling(window=window_size).std()
    upper_band = rolling_mean + (rolling_std * num_of_std)
    lower_band = rolling_mean - (rolling_std * num_of_std)

    trace = go.Scatter(
        x=df.index, y=upper_band, mode="lines", showlegend=False, name="BB_upper"
    )

    trace2 = go.Scatter(
        x=df.index, y=rolling_mean, mode="lines", showlegend=False, name="BB_mean"
    )

    trace3 = go.Scatter(
        x=df.index, y=lower_band, mode="lines", showlegend=False, name="BB_lower"
    )

    fig.append_trace(trace, 1, 1)  # plot in first row
    fig.append_trace(trace2, 1, 1)  # plot in first row
    fig.append_trace(trace3, 1, 1)  # plot in first row
    return fig


# Accumulation Distribution
def accumulation_trace(df):
    df["volume"] = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (
        df["high"] - df["low"]
    )
    trace = go.Scatter(
        x=df.index, y=df["volume"], mode="lines", showlegend=False, name="Accumulation"
    )
    return trace


# Commodity Channel Index
def cci_trace(df, ndays=5):
    TP = (df["high"] + df["low"] + df["close"]) / 3
    CCI = pd.Series(
        (TP - TP.rolling(window=10, center=False).mean())
        / (0.015 * TP.rolling(window=10, center=False).std()),
        name="cci",
    )
    trace = go.Scatter(x=df.index, y=CCI, mode="lines", showlegend=False, name="CCI")
    return trace


# Price Rate of Change
def roc_trace(df, ndays=5):
    N = df["close"].diff(ndays)
    D = df["close"].shift(ndays)
    ROC = pd.Series(N / D, name="roc")
    trace = go.Scatter(x=df.index, y=ROC, mode="lines", showlegend=False, name="ROC")
    return trace


# Stochastic oscillator %K
def stoc_trace(df):
    SOk = pd.Series((df["close"] - df["low"]) / (df["high"] - df["low"]), name="SO%k")
    trace = go.Scatter(x=df.index, y=SOk, mode="lines", showlegend=False, name="SO%k")
    return trace


# Momentum
def mom_trace(df, n=5):
    M = pd.Series(df["close"].diff(n), name="Momentum_" + str(n))
    trace = go.Scatter(x=df.index, y=M, mode="lines", showlegend=False, name="MOM")
    return trace


# Pivot points
def pp_trace(df, fig):
    PP = pd.Series((df["high"] + df["low"] + df["close"]) / 3)
    R1 = pd.Series(2 * PP - df["low"])
    S1 = pd.Series(2 * PP - df["high"])
    R2 = pd.Series(PP + df["high"] - df["low"])
    S2 = pd.Series(PP - df["high"] + df["low"])
    R3 = pd.Series(df["high"] + 2 * (PP - df["low"]))
    S3 = pd.Series(df["low"] - 2 * (df["high"] - PP))
    trace = go.Scatter(x=df.index, y=PP, mode="lines", showlegend=False, name="PP")
    trace1 = go.Scatter(x=df.index, y=R1, mode="lines", showlegend=False, name="R1")
    trace2 = go.Scatter(x=df.index, y=S1, mode="lines", showlegend=False, name="S1")
    trace3 = go.Scatter(x=df.index, y=R2, mode="lines", showlegend=False, name="R2")
    trace4 = go.Scatter(x=df.index, y=S2, mode="lines", showlegend=False, name="S2")
    trace5 = go.Scatter(x=df.index, y=R3, mode="lines", showlegend=False, name="R3")
    trace6 = go.Scatter(x=df.index, y=S3, mode="lines", showlegend=False, name="S3")
    fig.append_trace(trace, 1, 1)
    fig.append_trace(trace1, 1, 1)
    fig.append_trace(trace2, 1, 1)
    fig.append_trace(trace3, 1, 1)
    fig.append_trace(trace4, 1, 1)
    fig.append_trace(trace5, 1, 1)
    fig.append_trace(trace6, 1, 1)
    return fig


# MAIN CHART TRACES (STYLE tab)
def line_trace(df):
    trace = go.Scatter(
        x=df.index, y=df["close"], mode="lines", showlegend=False, name="line"
    )
    return trace


def area_trace(df):
    trace = go.Scatter(
        x=df.index, y=df["close"], showlegend=False, fill="toself", name="area"
    )
    return trace


def bar_trace(df):
    return go.Ohlc(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        increasing=dict(line=dict(color="#888888")),
        decreasing=dict(line=dict(color="#888888")),
        showlegend=False,
        name="bar",
    )


def colored_bar_trace(df):
    return go.Ohlc(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        showlegend=False,
        name="colored bar",
    )


def candlestick_trace(df):
    return go.Candlestick(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        increasing=dict(line=dict(color="#00ff00")),
        decreasing=dict(line=dict(color="white")),
        showlegend=False,
        name="candlestick",
    )


# For buy/sell modal
def ask_modal_trace(currency_pair, index):
    df = currency_pair_data[currency_pair].iloc[index - 10 : index]  # returns ten rows
    return go.Scatter(x=df.index, y=df["Ask"], mode="lines", showlegend=False)


# For buy/sell modal
def bid_modal_trace(currency_pair, index):
    df = currency_pair_data[currency_pair].iloc[index - 10 : index]  # returns ten rows
    return go.Scatter(x=df.index, y=df["Bid"], mode="lines", showlegend=False)


# returns modal figure for a currency pair
def get_modal_fig(currency_pair, index):
    fig = tools.make_subplots(
        rows=2, shared_xaxes=True, shared_yaxes=False, cols=1, print_grid=False
    )

    fig.append_trace(ask_modal_trace(currency_pair, index), 1, 1)
    fig.append_trace(bid_modal_trace(currency_pair, index), 2, 1)

    fig["layout"]["autosize"] = True
    fig["layout"]["height"] = 375
    fig["layout"]["margin"] = {"t": 5, "l": 50, "b": 0, "r": 5}
    fig["layout"]["yaxis"]["showgrid"] = True
    fig["layout"]["yaxis"]["gridcolor"] = "#3E3F40"
    fig["layout"]["yaxis"]["gridwidth"] = 1
    fig["layout"].update(paper_bgcolor="#21252C", plot_bgcolor="#21252C")

    return fig


# Returns graph figure
def get_fig(currency_pair, ask, bid, type_trace, studies, period):
    
    # Plot Data Initiation***

    df = getchartdata(currency_pair,'3m')
    df.rename(columns={'date':'Date'},inplace=True)
    
    df['Date']=pd.to_datetime(df['Date'])
    df.set_index('Date',inplace=True)

    subplot_traces = [  # first row traces
        "accumulation_trace",
        "cci_trace",
        "roc_trace",
        "stoc_trace",
        "mom_trace",
    ]
    selected_subplots_studies = []
    selected_first_row_studies = []
    row = 1  # number of subplots

    if studies:
        for study in studies:
            if study in subplot_traces:
                row += 1  # increment number of rows only if the study needs a subplot
                selected_subplots_studies.append(study)
            else:
                selected_first_row_studies.append(study)

    fig = tools.make_subplots(
        rows=row,
        shared_xaxes=True,
        shared_yaxes=True,
        cols=1,
        print_grid=False,
        vertical_spacing=0.12,
    )

    # Add main trace (style) to figure
    fig.append_trace(eval(type_trace)(df), 1, 1)

    # Add trace(s) on fig's first row
    for study in selected_first_row_studies:
        fig = eval(study)(df, fig)

    row = 1
    # Plot trace on new row
    for study in selected_subplots_studies:
        row += 1
        fig.append_trace(eval(study)(df), row, 1)

    fig["layout"][
        "uirevision"
    ] = "The User is always right"  # Ensures zoom on graph is the same on update
    fig["layout"]["margin"] = {"t": 50, "l": 50, "b": 50, "r": 25}
    fig["layout"]["autosize"] = True
    fig["layout"]["height"] = 400
    fig["layout"]["xaxis"]["rangeslider"]["visible"] = False
    fig["layout"]["xaxis"]["tickformat"] = "%m-%d-%y"
    fig["layout"]["yaxis"]["showgrid"] = True
    fig["layout"]["yaxis"]["gridcolor"] = "#3E3F40"
    fig["layout"]["yaxis"]["gridwidth"] = 1
    fig["layout"].update(paper_bgcolor="#21252C", plot_bgcolor="#21252C")

    return fig


# returns chart div
def chart_div(pair):
    return html.Div(
        id=pair + "graph_div",
        className="display-none",
        children=[
            # Menu for Currency Graph
            html.Div(
                id=pair + "menu",
                className="not_visible",
                children=[
                    # stores current menu tab
                    html.Div(
                        id=pair + "menu_tab",
                        children=["Studies"],
                        style={"display": "none"},
                    ),
                    html.Span(
                        "Style",
                        id=pair + "style_header",
                        className="span-menu",
                        n_clicks_timestamp=2,
                    ),
                    html.Span(
                        "Studies",
                        id=pair + "studies_header",
                        className="span-menu",
                        n_clicks_timestamp=1,
                    ),
                    # Studies Checklist
                    html.Div(
                        id=pair + "studies_tab",
                        children=[
                            dcc.Checklist(
                                id=pair + "studies",
                                options=[
                                    {
                                        "label": "Accumulation/D",
                                        "value": "accumulation_trace",
                                    },
                                    {
                                        "label": "Bollinger bands",
                                        "value": "bollinger_trace",
                                    },
                                    {"label": "MA", "value": "moving_average_trace"},
                                    {"label": "EMA", "value": "e_moving_average_trace"},
                                    {"label": "CCI", "value": "cci_trace"},
                                    {"label": "ROC", "value": "roc_trace"},
                                    {"label": "Pivot points", "value": "pp_trace"},
                                    {
                                        "label": "Stochastic oscillator",
                                        "value": "stoc_trace",
                                    },
                                    {
                                        "label": "Momentum indicator",
                                        "value": "mom_trace",
                                    },
                                ],
                                value=[],
                            )
                        ],
                        style={"display": "none"},
                    ),
                    # Styles checklist
                    html.Div(
                        id=pair + "style_tab",
                        children=[
                            dcc.RadioItems(
                                id=pair + "chart_type",
                                options=[
                                    {
                                        "label": "candlestick",
                                        "value": "candlestick_trace",
                                    },
                                    {"label": "line", "value": "line_trace"},
                                    {"label": "mountain", "value": "area_trace"},
                                    {"label": "bar", "value": "bar_trace"},
                                    {
                                        "label": "colored bar",
                                        "value": "colored_bar_trace",
                                    },
                                ],
                                value="colored_bar_trace",
                            )
                        ],
                    ),
                ],
            ),
            # Chart Top Bar
            html.Div(
                className="row chart-top-bar",
                children=[
                    html.Span(
                        id=pair + "menu_button",
                        className="inline-block chart-title",
                        children=f"{pair} ☰",
                        n_clicks=0,
                    ),
                    # Dropdown and close button float right
                    html.Div(
                        className="graph-top-right inline-block",
                        children=[
                            html.Div(
                                className="inline-block",
                                children=[
                                    dcc.Dropdown(
                                        className="dropdown-period",
                                        id=pair + "dropdown_period",
                                        options=[
                                            {"label": "5 min", "value": "5Min"},
                                            {"label": "15 min", "value": "15Min"},
                                            {"label": "30 min", "value": "30Min"},
                                        ],
                                        value="15Min",
                                        clearable=False,
                                    )
                                ],
                            ),
                            html.Span(
                                id=pair + "close",
                                className="chart-close inline-block float-right",
                                children="×",
                                n_clicks=0,
                            ),
                        ],
                    ),
                ],
            ),
            # Graph div
            html.Div(
                dcc.Graph(
                    id=pair + "chart",
                    className="chart-graph",
                    config={"displayModeBar": False, "scrollZoom": True},
                )
            ),
        ],
    )


# returns modal Buy/Sell
def modal(pair):
    return html.Div(
        id=pair + "modal",
        className="modal",
        style={"display": "none"},
        children=[
            html.Div(
                className="modal-content",
                children=[
                    html.Span(
                        id=pair + "closeModal", className="modal-close", children="×"
                    ),
                    html.P(id="modal" + pair, children=pair),
                    # row div with two div
                    html.Div(
                        className="row",
                        children=[
                            # graph div
                            html.Div(
                                className="six columns",
                                children=[
                                    dcc.Graph(
                                        id=pair + "modal_graph",
                                        config={"displayModeBar": False},
                                    )
                                ],
                            ),
                            # order values div
                            html.Div(
                                className="six columns modal-user-control",
                                children=[
                                    html.Div(
                                        children=[
                                            html.P("Volume"),
                                            dcc.Input(
                                                id=pair + "volume",
                                                className="modal-input",
                                                type="number",
                                                value=0.1,
                                                min=0,
                                                step=0.1,
                                            ),
                                        ]
                                    ),
                                    html.Div(
                                        children=[
                                            html.P("Type"),
                                            dcc.RadioItems(
                                                id=pair + "trade_type",
                                                options=[
                                                    {"label": "Buy", "value": "buy"},
                                                    {"label": "Sell", "value": "sell"},
                                                ],
                                                value="buy",
                                                labelStyle={"display": "inline-block"},
                                            ),
                                        ]
                                    ),
                                    html.Div(
                                        children=[
                                            html.P("SL TPS"),
                                            dcc.Input(
                                                id=pair + "SL",
                                                type="number",
                                                min=0,
                                                step=1,
                                            ),
                                        ]
                                    ),
                                    html.Div(
                                        children=[
                                            html.P("TP TPS"),
                                            dcc.Input(
                                                id=pair + "TP",
                                                type="number",
                                                min=0,
                                                step=1,
                                            ),
                                        ]
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="modal-order-btn",
                        children=html.Button(
                            "Order", id=pair + "button_order", n_clicks=0
                        ),
                    ),
                ],
            )
        ],
    )


# Dash App Layout
app.layout = html.Div(
    className="row",
    children=[
        # Interval component for live clock
        dcc.Interval(id="interval", interval=1 * 1000, n_intervals=0),
        # Interval component for ask bid updates
        dcc.Interval(id="i_bis", interval=1 * 30000, n_intervals=0),
        # Interval component for graph updates
        dcc.Interval(id="i_tris", interval=1 * 30000, n_intervals=0),
        # Interval component for graph updates
        dcc.Interval(id="i_news", interval=1 * 60000, n_intervals=0),
        # Left Panel Div
        html.Div(
            className="three columns div-left-panel",
            children=[
                # Ask Bid Currency Div
                html.H1(className="text-center",children=['Untouched Trading'],),
                html.Div(
                    className="div-currency-toggles",
                    children=[
                        html.P(
                            id="live_clock",
                            className="three-col",
                            children=datetime.datetime.now().strftime("%H:%M:%S"),
                        ),
                        html.P(className="three-col", children="Last"),
                        html.P(className="three-col", children="Change"),
                        html.Div(
                            id="pairs",
                            className="div-bid-ask",
                            children=[
                                get_row(first_ask_bid(pair))
                                for pair in currencies
                            ],
                        ),
                    ],
                ),
                # Div for News Headlines
                html.Div(
                    className="div-news",
                    children=[html.Div(id="news", children=update_news())],
                ),  
                # Div for Left Panel App Info
                html.Div(
                    className="div-info",
                    children=[
                        html.A(
                            html.Img(
                                className="logo",
                                src=app.get_asset_url("dash-logo-new.png"),
                            ),
                            href="https://plotly.com/dash/",
                        ),
                    ],
                ),
            ],
        ),
        # Right Panel Div
        html.Div(
            className="nine columns div-right-panel",
            children=[
                # Top Bar Div - Displays Balance, Equity, ... , Open P/L
                html.Div(
                    id="top_bar", className="row div-top-bar", children=get_top_bar()
                ),
                # Charts Div
                html.Div(
                    id="charts",
                    className="row",
                    children=[chart_div(pair) for pair in currencies],
                ),
                # Panel for orders
                html.Div(
                    id="bottom_panel",
                    className="row div-bottom-panel",
                    children=[
                        html.Div(
                            className="display-inlineblock",
                            children=[
                                dcc.Dropdown(
                                    id="dropdown_positions",
                                    className="bottom-dropdown",
                                    options=[
                                        {"label": "Open Positions", "value": "open"},
                                        {
                                            "label": "Closed Positions",
                                            "value": "closed",
                                        },
                                    ],
                                    value="open",
                                    clearable=False,
                                    style={"border": "0px solid black"},
                                )
                            ],
                        ),
                        html.Div(
                            className="display-inlineblock float-right",
                            children=[
                                dcc.Dropdown(
                                    id="closable_orders",
                                    className="bottom-dropdown",
                                    placeholder="Close order",
                                )
                            ],
                        ),
                        html.Div(id="orders_table", className="row table-orders"),
                    ],
                ),
            ],
        ),
        # Hidden div that stores all clicked charts (EURUSD, USDCHF, etc.)
        html.Div(id="charts_clicked", style={"display": "none"}),
        # Hidden div for each pair that stores orders
        html.Div(
            children=[
                html.Div(id=pair + "orders", style={"display": "none"})
                for pair in currencies
            ]
        ),
        html.Div([modal(pair) for pair in currencies]),
        # Hidden Div that stores all orders
        html.Div(id="orders", style={"display": "none"}),
    ],
)

# Dynamic Callbacks

# Replace currency pair row
def generate_ask_bid_row_callback(pair):
    def output_callback(n, i, bid, ask):
        return replace_row(pair, int(i), float(bid), float(ask))

    return output_callback


# returns string containing clicked charts
def generate_chart_button_callback():
    def chart_button_callback(*args):
        pairs = ""
        for i in range(len(currencies)):
            if args[i] > 0:
                pair = currencies[i]
                if pairs:
                    pairs = pairs + "," + pair
                else:
                    pairs = pair
        return pairs

    return chart_button_callback


# Function to update Graph Figure
def generate_figure_callback(pair):
    def chart_fig_callback(n_i, p, t, s, pairs, a, b, old_fig):

        if pairs is None:
            return {"layout": {}, "data": {}}

        pairs = pairs.split(",")
        if pair not in pairs:
            return {"layout": {}, "data": []}

        if old_fig is None or old_fig == {"layout": {}, "data": {}}:
            return get_fig(pair, a, b, t, s, p)

        fig = get_fig(pair, a, b, t, s, p)
        return fig

    return chart_fig_callback


# Function to close currency pair graph
def generate_close_graph_callback():
    def close_callback(n, n2):
        if n == 0:
            if n2 == 1:
                return 1
            return 0
        return 0

    return close_callback


# Function to open or close STYLE or STUDIES menu
def generate_open_close_menu_callback():
    def open_close_menu(n, className):
        if n == 0:
            return "not_visible"
        if className == "visible":
            return "not_visible"
        else:
            return "visible"

    return open_close_menu


# Function for hidden div that stores the last clicked menu tab
# Also updates style and studies menu headers
def generate_active_menu_tab_callback():
    def update_current_tab_name(n_style, n_studies):
        if n_style >= n_studies:
            return "Style", "span-menu selected", "span-menu"
        return "Studies", "span-menu", "span-menu selected"

    return update_current_tab_name


# Function show or hide studies menu for chart
def generate_studies_content_tab_callback():
    def studies_tab(current_tab):
        if current_tab == "Studies":
            return {"display": "block", "textAlign": "left", "marginTop": "30"}
        return {"display": "none"}

    return studies_tab


# Function show or hide style menu for chart
def generate_style_content_tab_callback():
    def style_tab(current_tab):
        if current_tab == "Style":
            return {"display": "block", "textAlign": "left", "marginTop": "30"}
        return {"display": "none"}

    return style_tab


# Open Modal
def generate_modal_open_callback():
    def open_modal(n):
        if n > 0:
            return {"display": "block"}
        else:
            return {"display": "none"}

    return open_modal


# Function to close modal
def generate_modal_close_callback():
    def close_modal(n, n2):
        return 0

    return close_modal


# Function for modal graph - set modal SL value to none
def generate_clean_sl_callback():
    def clean_sl(n):
        return 0

    return clean_sl


# Function for modal graph - set modal SL value to none
def generate_clean_tp_callback():
    def clean_tp(n):
        return 0

    return clean_tp


# Function to create figure for Buy/Sell Modal
def generate_modal_figure_callback(pair):
    def figure_modal(index, n, old_fig):
        if (n == 0 and old_fig is None) or n == 1:
            return get_modal_fig(pair, index)
        return old_fig  # avoid to compute new figure when the modal is hidden

    return figure_modal


# Function updates the pair orders div
def generate_order_button_callback(pair):
    def order_callback(n, vol, type_order, sl, tp, pair_orders, ask, bid):
        if n > 0:
            t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            l = [] if pair_orders is None else json.loads(pair_orders)
            price = bid if type_order == "sell" else ask

            if tp != 0:
                tp = (
                    price + tp * 0.001
                    if tp != 0 and pair[3:] == "JPY"
                    else price + tp * 0.00001
                )

            if sl != 0:
                sl = price - sl * 0.001 if pair[3:] == "JPY" else price + sl * 0.00001

            order = {
                "id": pair + str(len(l)),
                "time": t,
                "type": type_order,
                "volume": vol,
                "symbol": pair,
                "tp": tp,
                "sl": sl,
                "price": price,
                "profit": 0.00,
                "status": "open",
            }
            l.append(order)

            return json.dumps(l)

        return json.dumps([])

    return order_callback


# Function to update orders

def update_orders():
    idx=pd.IndexSlice

    a=api.get_activities()
    cols=['Activity Type','LeavesQty','CumQty','OrderId','order_status','price','qty','side','symbol','transaction_time','type']
    orderhist = pd.concat([pd.DataFrame([[v.activity_type,float(v.leaves_qty),float(v.cum_qty), v.order_id, v.order_status, float(v.price), v.qty, v.side, v.symbol, v.transaction_time, v.type]],columns=cols) for v in a])
    orderhist['transaction_time']=pd.to_datetime(orderhist['transaction_time'],format='%Y-%m-%dT%H:%M:%S.%f%Z')
    orderhist.sort_values(by=['transaction_time'],ascending=True,inplace=True)
    orderhist.set_index(['symbol','transaction_time'],inplace=True)
    orders=pd.DataFrame()
    r=0
    cols=['symbol','BuyDate','price','BuyQty','volume','SellDate','close price','sellqty']
    orders_list=[]
    for t in np.unique(np.asarray(orderhist.index.tolist()).astype(str)[:,0]):
        torder=0
        for transact in orderhist.loc[idx[t,:]].itertuples():
            if transact.side=='buy' and transact.type!='partial_fill':
                orders_list = [t,transact.Index,transact.price,transact.qty,transact.CumQty]
                torder+=1
            elif len(orders_list)!=0:
                orders_list.extend([transact.Index,transact.price,transact.qty])
        if len(orders_list)<len(cols):
            orders_list.extend([None]*(len(cols)-len(orders_list)))
        newrow = pd.DataFrame([orders_list],columns=cols).fillna(value=np.nan)
        orders = orders.append(newrow, ignore_index=True)
        orders_list=[]
    orders['profit']=(orders['close price']-orders['price'])*orders['volume']
    orders['status']=orders['SellDate'].isna().where(orders['SellDate'].isna(),'closed')
    orders['status']=orders['status'].where(orders['status']=='closed','open')
    orders['time']=orders['BuyDate'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
    orders['close time']=orders['SellDate'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
    orders['id']=orders['symbol']+orders['BuyDate'].apply(lambda x: x.strftime('%M%d'))
    orders=orders[orders['price'].notna()]
    currquotes = pd.DataFrame([[q.symbol,q.current_price,q.unrealized_pl] for q in api.list_positions()],columns=['symbol','current_ask','profit'])
    currquotes.set_index('symbol',inplace=True)
    for r in orders[orders['status']=='open'].itertuples():
        orders.loc[r.Index,'profit']=currquotes.at[r.symbol,'profit']
        orders.loc[r.Index,'close price']=currquotes.at[r.symbol,'current_ask']

    # for order in orders:
    #     if order["status"] == "open":
    #         type_order = order["type"]
    #         current_bid = current_bids[currencies.index(order["symbol"])]
    #         current_ask = current_asks[currencies.index(order["symbol"])]

    #         profit = (
    #             order["volume"]
    #             * 100000
    #             * ((current_bid - order["price"]) / order["price"])
    #             if type_order == "buy"
    #             else (
    #                 order["volume"]
    #                 * 100000
    #                 * ((order["price"] - current_ask) / order["price"])
    #             )
    #         )

    #         order["profit"] = "%.2f" % profit
    #         price = current_bid if order["type"] == "buy" else current_ask

    #         if order["id"] == id_to_close:
    #             order["status"] = "closed"
    #             order["close Time"] = datetime.datetime.now().strftime(
    #                 "%Y-%m-%d %H:%M:%S"
    #             )
    #             order["close Price"] = price

    #         if order["tp"] != 0 and price >= order["tp"]:
    #             order["status"] = "closed"
    #             order["close Time"] = datetime.datetime.now().strftime(
    #                 "%Y-%m-%d %H:%M:%S"
    #             )
    #             order["close Price"] = price

    #         if order["sl"] != 0 and order["sl"] >= price:
    #             order["status"] = "closed"
    #             order["close Time"] = datetime.datetime.now().strftime(
    #                 "%Y-%m-%d %H:%M:%S"
    #             )
    #             order["close Price"] = price

    return orders


# Function to update orders div
def generate_update_orders_div_callback():
    def update_orders_callback(*args):
        orders = []
        openpositions=api.list_positions()
        
        current_orders = args[-1]
        close_id = args[-2]
        args = args[:-2]  # contains list of orders for each pair + asks + bids
        len_args = len(args)
        current_bids = args[len_args // 3 : 2 * len_args]
        current_asks = args[2 * len_args // 3 : len_args]
        args = args[: len_args // 3]
        ids = []

        if current_orders is not None:
            orders = json.loads(current_orders)
            for order in orders:
                ids.append(
                    order["id"]  # ids that allready have been added to current orders
                )

        for list_order in args:  # each currency pair has its list of orders
            if list_order != "[]":
                list_order = json.loads(list_order)
                for order in list_order:
                    if order["id"] not in ids:  # only add new orders
                        orders.append(order)
        if len(orders) == 0:
            return None
        # we update status and profit of orders
        orders = update_orders()
        return json.dumps(orders)

    return update_orders_callback


# Resize pair div according to the number of charts displayed
def generate_show_hide_graph_div_callback(pair):
    def show_graph_div_callback(charts_clicked):


        charts_clicked = charts_clicked.split(",")  # [:4] max of 4 graph
        if pair not in charts_clicked:
            return "display-none"
        len_list = len(charts_clicked)
        classes = "chart-style"
        if len_list % 2 == 0:
            classes = classes + " six columns"
        elif len_list == 3:
            classes = classes + " four columns"
        else:
            classes = classes + " twelve columns"
        return classes

    return show_graph_div_callback


# Generate Buy/Sell and Chart Buttons for Left Panel
def generate_contents_for_left_panel():
    def show_contents(n_clicks):
        if n_clicks is None:
            return "display-none", "row summary"
        elif n_clicks % 2 == 0:
            return "display-none", "row summary"
        return "row details", "row summary-open"

    return show_contents


# Loop through all currencies
for pair in currencies:

    # Callback for Buy/Sell and Chart Buttons for Left Panel
    app.callback(
        [Output(pair + "contents", "className"), Output(pair + "summary", "className")],
        [Input(pair + "summary", "n_clicks")],
    )(generate_contents_for_left_panel())

    # Callback for className of div for graphs
    app.callback(
        Output(pair + "graph_div", "className"), [Input("charts_clicked", "children")]
    )(generate_show_hide_graph_div_callback(pair))

    # Callback to update the actual graph
    app.callback(
        Output(pair + "chart", "figure"),
        [
            Input("i_tris", "n_intervals"),
            Input(pair + "dropdown_period", "value"),
            Input(pair + "chart_type", "value"),
            Input(pair + "studies", "value"),
            Input("charts_clicked", "children"),
        ],
        [
            State(pair + "ask", "children"),
            State(pair + "bid", "children"),
            State(pair + "chart", "figure"),
        ],
    )(generate_figure_callback(pair))

    # updates the ask and bid prices
    app.callback(
        Output(pair + "row", "children"),
        [Input("i_bis", "n_intervals")],
        [
            State(pair + "index", "children"),
            State(pair + "bid", "children"),
            State(pair + "ask", "children"),
        ],
    )(generate_ask_bid_row_callback(pair))

    # close graph by setting to 0 n_clicks property
    app.callback(
        Output(pair + "Button_chart", "n_clicks"),
        [Input(pair + "close", "n_clicks")],
        [State(pair + "Button_chart", "n_clicks")],
    )(generate_close_graph_callback())

    # show or hide graph menu
    app.callback(
        Output(pair + "menu", "className"),
        [Input(pair + "menu_button", "n_clicks")],
        [State(pair + "menu", "className")],
    )(generate_open_close_menu_callback())

    # stores in hidden div name of clicked tab name
    app.callback(
        [
            Output(pair + "menu_tab", "children"),
            Output(pair + "style_header", "className"),
            Output(pair + "studies_header", "className"),
        ],
        [
            Input(pair + "style_header", "n_clicks_timestamp"),
            Input(pair + "studies_header", "n_clicks_timestamp"),
        ],
    )(generate_active_menu_tab_callback())

    # hide/show STYLE tab content if clicked or not
    app.callback(
        Output(pair + "style_tab", "style"), [Input(pair + "menu_tab", "children")]
    )(generate_style_content_tab_callback())

    # hide/show MENU tab content if clicked or not
    app.callback(
        Output(pair + "studies_tab", "style"), [Input(pair + "menu_tab", "children")]
    )(generate_studies_content_tab_callback())

    # show modal
    app.callback(Output(pair + "modal", "style"), [Input(pair + "Buy", "n_clicks")])(
        generate_modal_open_callback()
    )

    # set modal value SL to O
    app.callback(Output(pair + "SL", "value"), [Input(pair + "Buy", "n_clicks")])(
        generate_clean_sl_callback()
    )

    # set modal value TP to O
    app.callback(Output(pair + "TP", "value"), [Input(pair + "Buy", "n_clicks")])(
        generate_clean_tp_callback()
    )

    # hide modal
    app.callback(
        Output(pair + "Buy", "n_clicks"),
        [
            Input(pair + "closeModal", "n_clicks"),
            Input(pair + "button_order", "n_clicks"),
        ],
    )(generate_modal_close_callback())

    # updates modal figure
    app.callback(
        Output(pair + "modal_graph", "figure"),
        [Input(pair + "index", "children"), Input(pair + "Buy", "n_clicks")],
        [State(pair + "modal_graph", "figure")],
    )(generate_modal_figure_callback(pair))

    # each pair saves its orders in hidden div
    app.callback(
        Output(pair + "orders", "children"),
        [Input(pair + "button_order", "n_clicks")],
        [
            State(pair + "volume", "value"),
            State(pair + "trade_type", "value"),
            State(pair + "SL", "value"),
            State(pair + "TP", "value"),
            State(pair + "orders", "children"),
            State(pair + "ask", "children"),
            State(pair + "bid", "children"),
        ],
    )(generate_order_button_callback(pair))

# updates hidden div with all the clicked charts
app.callback(
    Output("charts_clicked", "children"),
    [Input(pair + "Button_chart", "n_clicks") for pair in currencies],
    [State("charts_clicked", "children")],
)(generate_chart_button_callback())

# updates hidden orders div with all pairs orders
app.callback(
    Output("orders", "children"),
    [Input(pair + "orders", "children") for pair in currencies]
    + [Input(pair + "bid", "children") for pair in currencies]
    + [Input(pair + "ask", "children") for pair in currencies]
    + [Input("closable_orders", "value")],
    [State("orders", "children")],
)(generate_update_orders_div_callback())

# Callback to update Orders Table
@app.callback(
    Output("orders_table", "children"),
    [Input("orders", "children"), Input("dropdown_positions", "value")],
)
def update_order_table(orders, position):
    headers = [
        "Order Id",
        "Time",
        "Volume",
        "Symbol",
        "Price",
        "Profit",
        "Status",
        "Close Time",
        "Close Price",
    ]

    # If there are no orders
    # if orders is None or orders is "[]":
    #     return [
    #         html.Table(html.Tr(children=[html.Th(title) for title in headers])),
    #         html.Div(
    #             className="text-center table-orders-empty",
    #             children=[html.P("No " + position + " positions data row")],
    #         ),
    #     ]

    rows = []
    list_order = update_orders()
    list_order = list_order[['id','time','volume','symbol','price','profit','status','close time','close price']]
    list_order = list_order.reindex(columns=['id','time','volume','symbol','price','profit','status','close time','close price'])
    list_order=json.loads(list_order.to_json(orient="records"))

    for order in list_order:
        tr_childs = []
        for attr in order:
            if order["status"] == position:
                tr_childs.append(html.Td(order[attr]))
        # Color row based on profitability of order
        if float(order["profit"]) >= 0:
            rows.append(html.Tr(className="profit", children=tr_childs))
        else:
            rows.append(html.Tr(className="no-profit", children=tr_childs))

    return html.Table(children=[html.Tr([html.Th(title) for title in headers])] + rows)


# Update Options in dropdown for Open and Close positions
@app.callback(Output("dropdown_positions", "options"), [Input("orders", "children")])
def update_positions_dropdown(orders):
    closeOrders = 0
    openOrders = 0
    if orders is not None:
        orders = json.loads(orders)
        for order in orders:
            if order["status"] == "closed":
                closeOrders += 1
            if order["status"] == "open":
                openOrders += 1
    return [
        {"label": "Open positions (" + str(openOrders) + ")", "value": "open"},
        {"label": "Closed positions (" + str(closeOrders) + ")", "value": "closed"},
    ]


# Callback to close orders from dropdown options
@app.callback(Output("closable_orders", "options"), [Input("orders", "children")])
def update_close_dropdown(orders):
    options = []
    if orders is not None:
        orders = json.loads(orders)
        for order in orders:
            if order["status"] == "open":
                options.append({"label": order["id"], "value": order["id"]})
    return options


# Callback to update Top Bar values
@app.callback(Output("top_bar", "children"), [Input("orders", "children")])
def update_top_bar(orders):
    # if orders is None or orders is "[]":
    #     return get_top_bar()
    return get_top_bar()

# Callback to update live clock
@app.callback(Output("live_clock", "children"), [Input("interval", "n_intervals")])
def update_time(n):
    return datetime.datetime.now().strftime("%H:%M:%S")


# Callback to update news
@app.callback(Output("news", "children"), [Input("i_news", "n_intervals")])
def update_news_div(n):
    return update_news()


if __name__ == "__main__":
    app.run_server(debug=True)
