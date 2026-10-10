"""User-facing error texts (Ukrainian). Every ErrorCode has one; each answers: what the app tried,
what happened, what to do next. Placeholders: the error's params plus {li_link} (author contact)."""

from mono_it_tax.config.enums import ErrorCode
from mono_it_tax.errors import AppError

LI_LINK_PLACEHOLDER = "li_link"

TOKEN_GUIDE_URL = "https://api.monobank.ua/"  # noqa: S105  (public page, not a secret)

ERROR_TEXTS: dict[ErrorCode, str] = {
    ErrorCode.NETWORK: (
        "Застосунок звернувся до {service} ({endpoint}) і після {attempts} спроб отримав помилку "
        "мережі. Ймовірно, проблема з інтернетом. Перевірте з'єднання і повторіть."
    ),
    ErrorCode.SERVICE_DOWN: (
        "Сервер {service} ({endpoint}) не відповів нормально після {attempts} спроб. "
        "Спробуйте пізніше; якщо не минає — напишіть автору: {li_link}"
    ),
    ErrorCode.TOKEN_REJECTED: (
        "{service} не прийняв токен: він недійсний, відкликаний або введений з помилкою. "
        "Створіть новий токен на " + TOKEN_GUIDE_URL + " і вставте його в .env (MONOBANK_TOKEN)."
    ),
    ErrorCode.RATE_LIMITED: (
        "{service} ({endpoint}) просить зачекати: після {attempts} спроб ліміт запитів не знявся. "
        "Зачекайте хвилину і повторіть."
    ),
    ErrorCode.API_CHANGED: (
        "Відповідь {service} ({endpoint}) має несподіваний вигляд: схоже, API змінилось. "
        "Оновіть застосунок або напишіть автору: {li_link}"
    ),
    ErrorCode.RATE_MISSING: (
        "Немає офіційного курсу НБУ для {currency} на {date}. Дохід у цій валюті не можна "
        "перерахувати в гривні. Спробуйте пізніше або напишіть автору: {li_link}"
    ),
    ErrorCode.UNSUPPORTED_CURRENCY: (
        "Банк повернув платіж у валюті з кодом {code}, яку застосунок ще не підтримує. "
        "Напишіть автору, щоб її додали: {li_link}"
    ),
    ErrorCode.STORE_UNREADABLE: (
        "Не вдалося прочитати локальні дані ({path}): файл пошкоджений або втрачено ключ "
        "шифрування. Можна видалити ці дані в меню «Мої дані» і завантажити їх з банку заново "
        "(це займе кілька хвилин)."
    ),
    ErrorCode.CONFIG_TOKEN_MISSING: (
        "MONOBANK_TOKEN не задано. Як його отримати (1-2 хвилини, безкоштовно):\n"
        "  1. Відкрийте " + TOKEN_GUIDE_URL + "\n"
        "  2. Увійдіть через застосунок monobank (підтвердіть вхід у застосунку).\n"
        "  3. Активуйте «Токен фізичної особи та ФОП».\n"
        "  4. Скопіюйте токен ОДРАЗУ: другий раз його не покажуть (до 5 токенів на акаунт).\n"
        "  5. Створіть файл .env у корені проєкту (за зразком .env.example) і додайте рядок "
        "MONOBANK_TOKEN=ваш_токен\n"
        "  6. Нікому не показуйте токен і не публікуйте .env."
    ),
    ErrorCode.CONFIG_RULES_MISSING: (
        "Немає файлу податкових правил {path} для потрібного року. Без нього застосунок не "
        "вгадує ставки. Оновіть застосунок або напишіть автору: {li_link}"
    ),
    ErrorCode.CONFIG_RULES_INVALID: (
        "Файл податкових правил {path} пошкоджений: {detail}. Виправте його або "
        "відновіть з репозиторію."
    ),
    ErrorCode.CONFIG_KEY_UNAVAILABLE: (
        "Не вдалося отримати ключ шифрування локальних даних: {detail}. Перевірте доступ до "
        "сховища паролів ОС або змініть KEY_STORAGE=file у .env."
    ),
    ErrorCode.MONTHS_NOT_REVIEWED: (
        "Не завершено перегляд місяців: {months}. Завантажте дані, позначте доходи і підтвердіть "
        "«готово» для кожного з цих місяців (навіть якщо доходів не було), потім повторіть."
    ),
    ErrorCode.UNKNOWN_ACCOUNT: (
        "Такого рахунку немає в списку. Оновіть сторінку і оберіть рахунки знову."
    ),
    ErrorCode.UNKNOWN_PAYMENT: (
        "Такого платежу немає в завантажених даних. Оновіть список платежів."
    ),
    ErrorCode.MONTH_NOT_FETCHED: (
        "Місяць {month} ще не завантажено повністю. Завантажте його з банку, а потім "
        "підтверджуйте «готово»."
    ),
    ErrorCode.JOB_NOT_FOUND: "Це завантаження не знайдено: можливо, застосунок було перезапущено.",
    ErrorCode.JOB_RUNNING: (
        "Завантаження вже триває. Дочекайтесь завершення або скасуйте його, потім почніть нове."
    ),
    ErrorCode.SELECTION_EMPTY: "Не обрано жодного місяця. Оберіть період або місяці.",
    ErrorCode.SELECTION_MULTI_YEAR: (
        "Можна обирати місяці лише одного року. Оберіть місяці одного календарного року."
    ),
    ErrorCode.DECL_PREVIOUS_REQUIRED: (
        "Для періоду {period} потрібна попередня декларація ({previous}). Введіть її рядки з "
        "електронного кабінету або дозвольте застосунку порахувати їх з банківських даних."
    ),
    ErrorCode.DECL_PREVIOUS_FORBIDDEN: (
        "Період {period} — перший у році: попередньої декларації не існує."
    ),
    ErrorCode.DECL_PREVIOUS_NOT_ADJACENT: (
        "Потрібна декларація за попередній період ({expected}), а вказано {got}."
    ),
    ErrorCode.DECL_ROW07_NOT_ZERO: (
        "У попередній декларації рядок {row} (дохід за ставкою 15%) не нульовий. Така ситуація "
        "не підтримується: зверніться до бухгалтера."
    ),
    ErrorCode.DECL_ROW_MISMATCH: (
        "У попередній декларації рядок {row} = {typed}, а за доходом має бути {expected}. "
        "Перевірте, чи правильно ви переписали суми."
    ),
    ErrorCode.DECL_NEGATIVE: "Сума в рядку {what} не може бути від'ємною.",
    ErrorCode.DECL_INCOME_OVER_LIMIT: (
        "Дохід {income} перевищує ліміт {limit} для групи. Така ситуація не підтримується: "
        "зверніться до бухгалтера."
    ),
    ErrorCode.DECL_RULES_YEAR: (
        "Правила для {rules_year} року не можна застосувати до декларації за {year} рік."
    ),
}


INTERNAL_ERROR_TEXT = (
    "Сталася неочікувана помилка. Дані не пошкоджені. Спробуйте повторити; якщо повторюється — "
    "напишіть автору (посилання внизу сторінки)."
)


def render_error(error: AppError, li_link: str) -> str:
    return ERROR_TEXTS[error.code].format(**error.params, **{LI_LINK_PLACEHOLDER: li_link})
