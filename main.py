from telebot import TeleBot, types
from PIL import Image
import io


TOKEN = '7038375691:AAH7IHF_qgRTnllsW8odBNuV0mNm9BZ6ZTY'
bot = TeleBot(TOKEN)

user_states = {}  # тут будем хранить информацию о действиях пользователя

# набор символов из которых составляем изображение
ASCII_CHARS = '@%#*+=-:. '


def resize_image(image, new_width=100):
    """
    Изменяет размер изображения, сохраняя пропорции.
    :param image: Исходное изображение.
    :param new_width: Новая ширина изображения.
    :return: Измененное изображение с новой шириной.
    """
    width, height = image.size
    ratio = height / width
    new_height = int(new_width * ratio)
    return image.resize((new_width, new_height))


def grayify(image):
    """
    Конвертирует изображение в оттенки серого.
    :param image:  Исходное изображение.
    :return: Изображение в оттенках серого.
    """
    return image.convert("L")


def image_to_ascii(image_stream, new_width=40):
    """
    Преобразует изображение в ASCII-арт.
    :param image_stream: Поток изображения.
    :param new_width: Ширина для преобразованного изображения.
    :return str: ASCII-арт, представляющий изображение.
    """
    # Переводим в оттенки серого
    image = Image.open(image_stream).convert('L')

    # меняем размер сохраняя отношение сторон
    width, height = image.size
    aspect_ratio = height / float(width)
    new_height = int(
        aspect_ratio * new_width * 0.55)  # 0,55 так как буквы выше чем шире
    img_resized = image.resize((new_width, new_height))

    img_str = pixels_to_ascii(img_resized)
    img_width = img_resized.width

    max_characters = 4000 - (new_width + 1)
    max_rows = max_characters // (new_width + 1)

    ascii_art = ""
    for i in range(0, min(max_rows * img_width, len(img_str)), img_width):
        ascii_art += img_str[i:i + img_width] + "\n"

    return ascii_art


def pixels_to_ascii(image):
    """
    Преобразует пиксели изображение в символы ASCII.
    :param image: Исходное изображение в оттенке серого.
    :return: Строка символов ASCII, представляющая изображение.
    """
    pixels = image.getdata()
    characters = ""
    for pixel in pixels:
        characters += ASCII_CHARS[pixel * len(ASCII_CHARS) // 256]
    return characters


# Огрубляем изображение
def pixelate_image(image, pixel_size):
    """
    Уменьшает разрешение изображения.
    :param image: Исходное изображение.
    :param pixel_size: Размер пикселя.
    :return: Изображение с измененным разрешением.
    """
    image = image.resize(
        (image.size[0] // pixel_size, image.size[1] // pixel_size),
        Image.NEAREST
    )
    image = image.resize(
        (image.size[0] * pixel_size, image.size[1] * pixel_size),
        Image.NEAREST
    )
    return image


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """
    Приветственное сообщение при вводе команды /start, /help.
    :param message: Команда от пользователя.
    :return: None
    """
    bot.reply_to(message, "Send me an image, and I'll provide options for you!")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """
    Принимает фото, и обрабатывает его.
    :param message: Фото от пользователя.
    :return: None
    """
    bot.reply_to(message, "I got your photo! Please choose what you'd like to do with it.",
                 reply_markup=get_options_keyboard())
    user_states[message.chat.id] = {'photo': message.photo[-1].file_id}


def get_options_keyboard():
    """
    Создает клавиатуру с вариантами действий (две кнопки).
    :return: Клавиатура с кнопками.
    """
    keyboard = types.InlineKeyboardMarkup()
    pixelate_btn = types.InlineKeyboardButton("Pixelate", callback_data="pixelate")
    ascii_btn = types.InlineKeyboardButton("ASCII Art", callback_data="ascii")
    keyboard.add(pixelate_btn, ascii_btn)
    return keyboard


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """
    Обрабатывает callback-запросы от кнопок интерфейса.
    :param call: Callback-запрос от пользователя.
    :return: None
    """
    if call.data == "pixelate":
        bot.answer_callback_query(call.id, "Pixelating your image...")
        pixelate_and_send(call.message)
    elif call.data == "ascii":
        bot.reply_to(call.message, f"The default character set: {ASCII_CHARS}, if you want to specify your"
                                   f" characters, click yes", reply_markup=get_symbol_keyboard())
    elif call.data == 'No':
        ascii_and_send(call.from_user.id)
    elif call.data == 'Yes':
        bot.answer_callback_query(call.id, 'Enter the desired character set:')
        user_states[call.from_user.id]['Waiting for custom symbols'] = True


def get_symbol_keyboard():
    """
    Создает клавиатуру для выбора символов пользователем.
    :return: Клавиатуру с интерфейсом (Кнопки Yes и NO)
    """
    keyboard = types.InlineKeyboardMarkup()
    no_button = types.InlineKeyboardButton('Yes', callback_data='Yes')
    yes_button = types.InlineKeyboardButton("No", callback_data='No')
    keyboard.add(no_button, yes_button)
    return keyboard

@bot.message_handler(content_types=['text'])
def input_simbols(message):
    """
    Обрабатывает выбор пользователя (NO), и передает введенные символы в метод преобразования в ASCII-арт.
    :param message: Сообщение от пользователя с введенными символами.
    :return: None
    """
    if message.from_user.id in user_states and  'Waiting for custom symbols' in user_states[message.from_user.id]:
        global ASCII_CHARS
        user_ASCII_CHARS = ASCII_CHARS
        ASCII_CHARS = message.text
        bot.send_message(message.chat.id, f"Simbols set to: {ASCII_CHARS}" )
        bot.send_message(message.chat.id, "Converting your image to ASCII art...")
        ascii_and_send(message.from_user.id)
        ASCII_CHARS = user_ASCII_CHARS

def pixelate_and_send(message):
    """
    Уменьшает разрешение изображения и отправляет пользователю.
    :param message: Сообщение от пользователя с фотографией.
    :return: None
    """
    photo_id = user_states[message.chat.id]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    pixelated = pixelate_image(image, 20)

    output_stream = io.BytesIO()
    pixelated.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(message.chat.id, output_stream)


def ascii_and_send(message):
    """
    Обрабатывает сообщение и выполняет конвертацию в ASCII-арт.
    :param message: Сообщение от пользователя с фотографией.
    :return: None
    """
    photo_id = user_states[message]['photo']
    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)

    image_stream = io.BytesIO(downloaded_file)
    ascii_art = image_to_ascii(image_stream)
    bot.send_message(message, f"```\n{ascii_art}\n```", parse_mode="MarkdownV2")

bot.polling(none_stop=True)