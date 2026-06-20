<?php

define('BASE_PATH', dirname(__DIR__));
define('APP_PATH', BASE_PATH . DIRECTORY_SEPARATOR . 'app');
define('TEMPLATE_PATH', BASE_PATH . DIRECTORY_SEPARATOR . 'templates');

function load_env(string $path): void
{
    if (!is_file($path)) {
        return;
    }

    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);

    foreach ($lines as $line) {
        $line = trim($line);

        if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) {
            continue;
        }

        [$key, $value] = explode('=', $line, 2);
        $key = trim($key);
        $value = trim($value, " \t\n\r\0\x0B\"'");

        if ($key !== '' && getenv($key) === false) {
            putenv($key . '=' . $value);
            $_ENV[$key] = $value;
        }
    }
}

function env_value(string $key, mixed $default = null): mixed
{
    $value = getenv($key);

    return $value === false ? $default : $value;
}

function url_for(string $page = 'home'): string
{
    return $page === 'home' ? 'index.php' : 'index.php?page=' . urlencode($page);
}

function asset(string $path): string
{
    return 'static/' . ltrim($path, '/');
}

load_env(BASE_PATH . DIRECTORY_SEPARATOR . '.env');
