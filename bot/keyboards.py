from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data="standup:send"),
                InlineKeyboardButton(text="✏ Изменить", callback_data="standup:edit"),
            ]
        ]
    )
