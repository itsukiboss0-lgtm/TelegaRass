from aiogram.fsm.state import State, StatesGroup

class TextMessageStates(StatesGroup):
    choosing_type = State()
    waiting_ordinary = State()
    waiting_count = State()
    waiting_message_n = State()
    waiting_main_message = State()
    waiting_buttons_count = State()
    waiting_button_name = State()
    waiting_button_url = State()
    showing_example = State()
    going_home = State()

class AccountStates(StatesGroup):
    main = State()
    adding_phone = State()
    waiting_code = State()
    waiting_2fa_password = State()
    deleting_confirm = State()

class MailingStates(StatesGroup):
    panel = State()
    autostop_setting = State()
    mention_setting = State()
    statistics_view = State()
    cycle_interval_setting = State()
    message_interval_setting = State()
    schedule_custom_time = State()

class GroupStates(StatesGroup):
    main = State()

class TariffStates(StatesGroup):
    main = State()
    choosing_duration = State()
    payment_stars = State()