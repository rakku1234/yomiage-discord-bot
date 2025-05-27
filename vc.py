import aiofiles
import asyncio
import discord
import glob
import kanalizer
import os
import re
import tempfile
import time
from aivisspeech import aivisspeech
from aquestalk import aquestalk1, aquestalk2
from collections import defaultdict
from config import Config
from database import Database
from loguru import logger
from text_to_speech import text_to_speech
from voicevox import voicevox

current_voice_settings = {}
message_queues = defaultdict(asyncio.Queue)
reading_tasks = {}
config = Config.load_config()
debug = config['debug']

async def speak_in_voice_channel(voice_client: discord.VoiceClient, message: str, voice_name: str, pitch: int, speed: int, engine: str):
    if not voice_client.is_connected():
        return

    message = kana_convert(message)

    if debug:
        logger.debug(f"音声合成開始: {message} - 使用する音声合成エンジン: {engine}")
        start_time = time.time()

    try:
        match engine:
            case 'voicevox':
                if not config['engine_enabled']['voicevox']:
                    return
                audio = voicevox(message, int(voice_name), pitch, speed)
            case 'aivisspeech':
                if not config['engine_enabled']['aivisspeech']:
                    return
                audio = aivisspeech(message, int(voice_name), pitch, speed)
            case 'aquestalk1':
                if not config['engine_enabled']['aquestalk1']:
                    return
                audio = aquestalk1(message, voice_name, int(speed))
            case 'aquestalk2':
                if not config['engine_enabled']['aquestalk2']:
                    return
                audio = aquestalk2(message, voice_name, int(speed))
            case _:
                raise ValueError(f"無効なエンジン: {engine}")

        audio_data = await audio.get_audio()
        async with aiofiles.tempfile.NamedTemporaryFile(suffix='.wav', prefix='yomiage_', delete=False) as temp:
            await temp.write(audio_data)
            audio_file = temp.name

        if engine.startswith('aquestalk'):
            audio_file = await pitch_convert(audio_file, pitch)

        if debug:
            end_time = time.time()
            logger.debug(f"音声合成完了 - 所要時間: {end_time - start_time}秒 ファイル名: {audio_file}")

        future = asyncio.Future()
        def after_playing(error):
            if error:
                future.set_exception(error)
            else:
                future.set_result(None)

        while voice_client.is_playing():
            await asyncio.sleep(0.1)

        voice_client.play(discord.FFmpegPCMAudio(audio_file, before_options='-guess_layout_max 0'), after=after_playing)
        await future
    except Exception as e:
        logger.error(f"音声合成エラー: {e}\n入力メッセージ: {message}")

db = Database()

async def process_message_queue(guild_id: int):
    while True:
        try:
            message_data = await message_queues[guild_id].get()
            if message_data is None:
                break

            text, voice_name, pitch, speed, voice_client, engine = message_data

            await speak_in_voice_channel(voice_client, text, voice_name, pitch, speed, engine)
            if debug:
                logger.debug('音声再生が完了しました')

            message_queues[guild_id].task_done()
        except Exception as e:
            logger.error(f"メッセージキュー処理エラー: {e}")
            continue

async def read_message(message: str | discord.Message, guild: discord.Guild = None, author: discord.Member = None, channel: discord.TextChannel = None) -> None:
    if isinstance(message, str):
        text = message
    else:
        if message.author.bot:
            return

        channels = await db.get_read_channels()
        if message.guild.id not in channels or message.channel.id != channels[message.guild.id][1]:
            return

        guild = message.guild
        author = message.author
        channel = message.channel
        text = message.content.replace('\n', ' ')

    voice_client = guild.voice_client
    if voice_client is None or not voice_client.is_connected():
        return

    dictionary_replacements = await db.get_dictionary_replacements(guild.id)
    for original, replacement in dictionary_replacements.items():
        text = text.replace(original, replacement)

    voice_settings = current_voice_settings.get((guild.id, author.id))
    if voice_settings is None and author:
        voice_settings = await db.get_voice_settings(guild.id, author.id)
        if voice_settings:
            current_voice_settings[(guild.id, author.id)] = voice_settings

    voice_name = '2'
    pitch = 100
    speed = 1.0
    engine = 'voicevox'

    if voice_settings:
        voice_name, pitch, speed, engine = voice_settings

    for match in re.finditer(r'<@!?(\d+)>', text):
        user_id = int(match.group(1))
        user = guild.get_member(user_id)
        if user:
            text = text.replace(match.group(0), user.display_name)
    
    for channel_id_str in re.findall(r'<#(\d+)>', text):
        channel_id = int(channel_id_str)
        channel = guild.get_channel(channel_id)
        if channel:
            cleaned_channel_name = re.sub(r'[\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\u2600-\u26FF\u2700-\u27BF]', '', channel.name)
            text = text.replace(f'<#{channel_id_str}>', cleaned_channel_name)

    text = re.sub(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:\/[^\s]*)?', 'URL省略', text)

    text = re.sub(r'<:[a-zA-Z0-9_]+:[0-9]+>', '', text)

    if len(text) == 0:
        return

    if len(text) >= config['discord']['max_length']:
        text = text[:config['discord']['max_length']] + '。以下省略'

    if engine.startswith('aquestalk'):
        text = text_to_speech().convert(text)

    await message_queues[guild.id].put((text, voice_name, pitch, speed, voice_client, engine))

    if guild.id not in reading_tasks or reading_tasks[guild.id].done():
        reading_tasks[guild.id] = asyncio.create_task(process_message_queue(guild.id))

def update_voice_settings(guild_id: int, user_id: int, voice_name: str, pitch: int, speed: int, engine: str):
    current_voice_settings[(guild_id, user_id)] = (voice_name, pitch, speed, engine)

async def cleanup_temp_files() -> None:
    while True:
        for file in glob.glob(os.path.join(tempfile.gettempdir(), 'yomiage_*.wav')):
            try:
                os.unlink(file)
                if debug:
                    logger.debug(f"一時ファイルを削除しました: {file}")
            except Exception as e:
                logger.error(f"一時ファイルの削除に失敗しました: {e}")
        await asyncio.sleep(300)

async def pitch_convert(file_path: str, pitch: int) -> str:
    temp_file = file_path.replace('.wav', '_temp.wav')
    process = await asyncio.create_subprocess_exec(
        'ffmpeg', '-i', file_path,
        '-af', f'asetrate=8000*{pitch}/100,atempo=100/{pitch}',
        '-ar', '8000', '-ac', '1', '-f', 'wav', temp_file,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process.wait()
    os.replace(temp_file, file_path)
    return file_path

def kana_convert(message: str) -> str:
    def replace_english(match: re.Match):
        english_word = match.group(0)
        return kanalizer.convert(english_word.lower())

    result = re.sub(r'[a-zA-Z]+', replace_english, message)
    return result
