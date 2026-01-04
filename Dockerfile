FROM python:3.10-slim

# Метаданные
LABEL maintainer="alexdiptan"
LABEL description="Trading Journal Telegram Bot"

# Устанавливаем таймзону МСК
ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости (только необходимые)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY bot.py database.py analytics.py config.py ./

# Создаём непривилегированного пользователя
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

USER botuser

# Запуск бота
CMD ["python", "-u", "bot.py"]
