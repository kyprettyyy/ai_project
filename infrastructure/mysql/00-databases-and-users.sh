#!/usr/bin/env bash
set -euo pipefail

: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD is required}"
: "${GATEWAY_DB_PASSWORD:?GATEWAY_DB_PASSWORD is required}"
: "${EVALUATION_DB_PASSWORD:?EVALUATION_DB_PASSWORD is required}"

mysql --protocol=socket -uroot -p"${MYSQL_ROOT_PASSWORD}" <<EOSQL
CREATE DATABASE IF NOT EXISTS evalroute_gateway
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS evalroute_evaluation
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'evalroute_gateway'@'%' IDENTIFIED BY '${GATEWAY_DB_PASSWORD}';
CREATE USER IF NOT EXISTS 'evalroute_evaluation'@'%' IDENTIFIED BY '${EVALUATION_DB_PASSWORD}';
GRANT ALL PRIVILEGES ON evalroute_gateway.* TO 'evalroute_gateway'@'%';
GRANT ALL PRIVILEGES ON evalroute_evaluation.* TO 'evalroute_evaluation'@'%';
FLUSH PRIVILEGES;
EOSQL
