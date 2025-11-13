#!/usr/bin/env bash


BACKUP_DIR_PATH='/backups'
# Detectar entorno desde variable de entorno o usar 'unknown'
BACKUP_ENV="${BACKUP_ENV:-unknown}"
BACKUP_FILE_PREFIX="${BACKUP_ENV}_backup"
