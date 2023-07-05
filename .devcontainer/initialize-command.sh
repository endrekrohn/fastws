#!/bin/sh

## If .env does not exist, create it
if [[ ! -e ./.devcontainer/.env ]]; then
    sed '/Optional/,$ s/./#&/' .devcontainer/.env.example > .devcontainer/.env
fi