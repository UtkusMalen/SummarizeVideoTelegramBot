import asyncio
import logging
import sys
from os import getenv
import os
import re
import google.generativeai as genai
import yt_dlp
import whisper
from langdetect import detect
from bs4 import BeautifulSoup



from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Filter
from aiogram.types import Message
from dotenv import load_dotenv



load_dotenv()

TOKEN = getenv('BOT_TOKEN')
genai.configure(api_key=getenv('GEMINI_TOKEN'))

dp = Dispatcher()
semaphore = asyncio.Semaphore(1)

@dp.message(CommandStart())
async def command_start_handler(message: Message):
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!\njust send me a youtube link to summize all content from it")

@dp.message(lambda message: "youtube.com" in message.text.lower() or "youtu.be" in message.text.lower())
async def check_for_youtube_url(message: Message):
    url = message.text
    match = re.search(r"(?:v=|\/)([a-zA-Z0-9_-]{11})", url)
    video_path = None
    if match:
        await message.answer(f"Summarizing video...\nIt can take a {html.bold("few")} minutes. Please wait.")
        try:
            video_path = await download_youtube_video(url)
            text = await transcribe_video(video_path)
            summary = await summarize_youtube_video(text)
            await message.answer(summary)
        except Exception as e:
            await message.answer(f"An error occurred while processing the video")
            logging.error(f"An error occurred while processing the video: {e}")
        finally:
            if video_path and os.path.exists(video_path):
                os.remove(video_path)
                logging.info(f"Deleted video file {video_path}")
    else:
        await message.answer("Invalid YouTube URL.")
        logging.warning(f"Invalid YouTube URL")

async def download_youtube_video(url):
    output_path = "./downloads"
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        logging.info(f"Created directory: {output_path}")
    os.makedirs(output_path, exist_ok=True)
    filepath_template = f"{output_path}/%(title)s.%(ext)s"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filepath_template,
        'quiet': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            logging.info(f"Downloaded video successfully: {downloaded_file}")
            return downloaded_file
    except yt_dlp.utils.DownloadError as e:
        logging.error(f"An error occurred while downloading the video: {e}")
        raise RuntimeError("Failed to download the video.") from e

async def transcribe_video(video_path):
    model = whisper.load_model("base")
    result = model.transcribe(video_path)
    logging.info(f"Transcribed video successfully")
    print(result["text"])
    return result["text"]

async def sanitize_text(text):
    allowed_tags = {'b', 'i', 'u', 'a', 'code', 'pre', 'tg-spoiler'}
    soup = BeautifulSoup(text, 'html.parser')
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    return str(soup)

async def summarize_youtube_video(text):
    language = detect(text)
    print(language)
    if language == "uk":
        language = "Українській"

    prompt = (
        f"Please summarize the following text into a concise and well-structured format, "
        f"emphasizing the key points and maintaining a logical flow. Organize the summary like a brief outline or structured notes, highlighting:\n"
        f"dont use ```html at the beginning and end of the text\n"
        f"1. The main idea or purpose of the text.\n"
        f"2. The key arguments, points, or topics discussed.\n"
        f"3. Any significant conclusions, implications, or outcomes.\n\n"
        f"Use HTML formatting to emphasize key points:\n"
        f"""Use only the following HTML tags to format the text:
        - <b> for bold
        - <i> for italic
        - <u> for underline
        - <a> for hyperlinks
        - <code> for inline code
        - <pre> for preformatted blocks
        - <tg-spoiler> for hidden text
        """
        f"- Use <b>bold</b> for the main idea or headings.\n"
        f"- Use <i>italic</i> for significant conclusions or emphasis.\n"
        f"- Organize key points as a bulleted list using <ul><li>...</li></ul>.\n\n"
        f"Ensure the summary is in {language}.\n\n"
        f"Text: {text}"
    )
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    formatted_response = await sanitize_text(response.text)
    return formatted_response

async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())