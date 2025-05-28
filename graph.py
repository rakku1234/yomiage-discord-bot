import aiofiles
import asyncio
import json
import os
import plotly.graph_objects as go
from datetime import datetime, timedelta
from loguru import logger

class SynthesisTimeGraph:
    def __init__(self, json_file='synthesis_times.json'):
        self.json_file = json_file
        if not os.path.exists(self.json_file):
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    async def add_point(self, duration: float):
        async with aiofiles.open(self.json_file, encoding='utf-8') as f:
            data = json.loads(await f.read())

        now = datetime.now()
        data.append({
            'time': now.isoformat(),
            'duration': duration
        })

        async with aiofiles.open(self.json_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))

    async def plot_graph(self):
        try:
            async with aiofiles.open(self.json_file, encoding='utf-8') as f:
                data = json.loads(await f.read())
        except (FileNotFoundError, json.JSONDecodeError):
            return

        if not data:
            return

        data.sort(key=lambda x: x['time'])

        yesterday = datetime.now() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        filtered_data = [
            d for d in data 
            if yesterday_start <= datetime.fromisoformat(d['time']) <= yesterday_end
        ]

        if not filtered_data:
            return

        times = [datetime.fromisoformat(d['time']) for d in filtered_data]
        durations = [d['duration'] for d in filtered_data]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=times,
            y=durations,
            mode='lines',
            name='処理時間',
            line=dict(color='blue')
        ))

        fig.update_layout(
            title='音声合成処理時間の推移（24時間）',
            xaxis_title='時間',
            yaxis_title='処理時間（秒）',
            xaxis=dict(
                tickformat='%H:%M',
                tickmode='auto',
                nticks=12
            ),
            showlegend=True,
            template='plotly_white'
        )

        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

        yesterday_date = yesterday.strftime('%Y-%m-%d')
        graph_file = os.path.join('graph', f"{yesterday_date}-synthesis-time-graph.html")
        html_content = fig.to_html(include_plotlyjs=True, full_html=True)

        async with aiofiles.open(graph_file, 'w', encoding='utf-8') as f:
            await f.write(html_content)

        async with aiofiles.open(self.json_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps([], ensure_ascii=False, indent=2))

        return graph_file

async def generate_daily_graph():
    graph = SynthesisTimeGraph()

    while True:
        now = datetime.now()
        next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        graph_file = await graph.plot_graph()
        if graph_file:
            logger.info(f"日次グラフを生成しました: {graph_file}")
        else:
            logger.warning("グラフの生成に失敗しました（データがありません）")
