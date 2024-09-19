import logging
import os
from docx import Document

import fitz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import ollama
import nest_asyncio

nest_asyncio.apply()

# Включаем ведение журнала
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Токен, который вы получили от @BotFather
TOKEN = '7172385372:AAETZ_QzAfjJIpZLLfHiLM0ZmDUJhi2_0GA'  # Replace with your actual token

# Словарь для хранения данных пользователей
user_ids = {}
context_memory = {}
user_files = {}

# Функция для обработки команды /start
async def start(update: Update, context) -> None:
    await update.message.reply_text('Привет! Я чат-бот. Чем могу помочь?')

# Функция для обработки обычных сообщений
async def handle_message(update: Update, context):
    user_id = update.effective_user.id
    if user_id not in user_ids:
        user_ids[user_id] = {'last_message': None, 'preferences': {}}
        context_memory[user_id] = []

    message_text = update.message.text
    context_messages = context_memory[user_id]

    # Добавляем новое сообщение в контекст
    context_messages.append({'role': 'user', 'content': message_text})

    # Ограничиваем историю контекста последними 8 сообщениями
    context_memory[user_id] = context_messages[-8:]

    try:
        # Call the ollama.chat function with the context messages
        response = ollama.chat(model='llama3:latest', messages=context_memory[user_id])
        # Отправляем ответ пользователю
        await update.message.reply_text(response['message']['content'])
    except Exception as e:
        logging.error(f"Error while getting response from ollama: {e}")
        await update.message.reply_text('Произошла ошибка, попробуйте позже.')


# Функция для обработки загруженных файлов
async def handle_file(update: Update, context) -> None:
    file = update.message.document

    if not file:
        logging.error("No document found in update.message")
        return

    file_path = await file.get_file()

    # Ensure the 'downloads' directory exists
    os.makedirs('downloads', exist_ok=True)

    file_name = os.path.join("downloads", file.file_name)
    await file_path.download_to_drive(file_name)

    text = extract_text_from_file(file_name)
    user_id = update.effective_user.id

    if user_id not in user_files:
        user_files[user_id] = []
    user_files[user_id].append(text)

    await update.message.reply_text(f'Файл {file.file_name} загружен и проанализирован.')

    # Получение краткого описания содержания файла
    summary = summarize_text(text)
    await update.message.reply_text(f'Описание файла: {summary}')

    # Сохранение файла в контекст пользователя
    if user_id not in context_memory:
        context_memory[user_id] = []

    context_memory[user_id].append({'role': 'system', 'content': f'Документ содержит: {text}'})

    # Подтверждение использования документа
    await update.message.reply_text(
        'Документ добавлен в контекст. Теперь вы можете задавать вопросы по его содержанию.')


def extract_text_from_file(file_path):
    text = ""
    if file_path.endswith('.pdf'):
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
    elif file_path.endswith('.docx'):
        doc = Document(file_path)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    elif file_path.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()

    # Добавьте обработку других типов файлов, если необходимо
    return text


def summarize_text(text):
    prompt = f"Опиши в одном предложении содержание следующего текста: {text}"
    response = ollama.chat(model='llama3:latest', messages=[{'role': 'user', 'content': prompt}])
    summary = response['message']['content']
    return summary

# Основная функция
async def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

