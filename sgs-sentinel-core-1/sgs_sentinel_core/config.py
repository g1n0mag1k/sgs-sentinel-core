# Configuration settings for the application

import os

class Config:
    DEBUG = os.getenv('DEBUG', 'False') == 'True'
    DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///default.db')
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key')
    API_VERSION = os.getenv('API_VERSION', 'v1')
    # Add more configuration variables as needed

# You can also create specific configurations for different environments
class DevelopmentConfig(Config):
    DEBUG = True
    DATABASE_URI = os.getenv('DEV_DATABASE_URI', 'sqlite:///dev.db')

class TestingConfig(Config):
    TESTING = True
    DATABASE_URI = os.getenv('TEST_DATABASE_URI', 'sqlite:///test.db')

class ProductionConfig(Config):
    DATABASE_URI = os.getenv('PROD_DATABASE_URI', 'sqlite:///prod.db')