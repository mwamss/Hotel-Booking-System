<?php

require_once __DIR__ . DIRECTORY_SEPARATOR . 'config.php';

$conn = new mysqli(
    env_value('DB_HOST', 'localhost'),
    env_value('DB_USERNAME', 'root'),
    env_value('DB_PASSWORD', ''),
    env_value('DB_DATABASE', 'hotel_booking'),
    (int) env_value('DB_PORT', 3306)
);

if ($conn->connect_error) {
    die('Connection failed: ' . $conn->connect_error);
}

$conn->set_charset('utf8mb4');
