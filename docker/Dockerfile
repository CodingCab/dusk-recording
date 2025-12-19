# Dusk Recording Container
# Provides headless Chrome with virtual display and screen recording

FROM php:8.3-cli

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Virtual display
    xvfb \
    x11-utils \
    # Chrome dependencies
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    # Video recording
    ffmpeg \
    # PHP extensions
    libzip-dev \
    libpng-dev \
    libjpeg-dev \
    # Python
    python3 \
    python3-pip \
    # Utilities
    git \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+') \
    && DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION%.*.*}") \
    && wget -q "https://storage.googleapis.com/chrome-for-testing-public/${DRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /tmp \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver*

# Install PHP extensions
RUN docker-php-ext-install pdo pdo_mysql zip gd pcntl

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Create working directories
RUN mkdir -p /app /recordings

# Copy Python scripts
COPY entrypoint.py /usr/local/bin/entrypoint.py
COPY record_test.py /usr/local/bin/record_test.py
RUN chmod +x /usr/local/bin/entrypoint.py /usr/local/bin/record_test.py

WORKDIR /app

# Environment
ENV DISPLAY=:99
ENV DUSK_DRIVER_URL=http://localhost:9515
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python3", "/usr/local/bin/entrypoint.py"]
CMD ["--help"]
