#!/bin/bash

usage() {
    echo "Usage:"
    echo "  $0 -u|--user username"
    echo "  $0 -g|--group groupname"
    echo
    echo "Only one flag is allowed: either --user or --group."
    exit 1
}

if [ "$#" -ne 2 ]; then
    usage
fi

case "$1" in
    -u|--user)
        TARGET_TYPE="user"
        TARGET_NAME="$2"
        ;;
    -g|--group)
        TARGET_TYPE="group"
        TARGET_NAME="$2"
        ;;
    *)
        usage
        ;;
esac

if [ "$TARGET_TYPE" = "user" ]; then
    if ! id "$TARGET_NAME" &>/dev/null; then
        echo "Error: user '$TARGET_NAME' does not exist"
        exit 1
    fi

    usermod -aG sudo "$TARGET_NAME"

    if [ $? -eq 0 ]; then
        echo "User '$TARGET_NAME' added to sudo group"
    else
        echo "Error: failed to add user '$TARGET_NAME' to sudo group"
        exit 1
    fi
fi

if [ "$TARGET_TYPE" = "group" ]; then
    if ! getent group "$TARGET_NAME" &>/dev/null; then
        echo "Error: group '$TARGET_NAME' does not exist"
        exit 1
    fi

    SUDOERS_FILE="/etc/sudoers.d/$TARGET_NAME"

    echo "%$TARGET_NAME ALL=(ALL:ALL) ALL" > "$SUDOERS_FILE"
    chmod 440 "$SUDOERS_FILE"

    if visudo -cf "$SUDOERS_FILE" &>/dev/null; then
        echo "Group '$TARGET_NAME' added to sudoers"
    else
        rm -f "$SUDOERS_FILE"
        echo "Error: invalid sudoers file"
        exit 1
    fi
fi
