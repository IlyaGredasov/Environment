#!/bin/bash

usage() {
    echo "Usage:"
    echo "  $0 username"
    echo "  $0 username -g|--group groupname"
    echo
    echo "Behavior:"
    echo "  - If user does not exist: creates user"
    echo "  - If user exists + group specified: adds user to group"
    echo "  - If group does not exist: creates group automatically"
    echo "  - If no group specified: default user creation only"
    exit 1
}

if [ "$#" -ne 1 ] && [ "$#" -ne 3 ]; then
    usage
fi

USERNAME="$1"
GROUPNAME=""

if [ "$#" -eq 3 ]; then
    case "$2" in
        -g|--group)
            GROUPNAME="$3"
            ;;
        *)
            usage
            ;;
    esac
fi

if [ -n "$GROUPNAME" ]; then
    if ! getent group "$GROUPNAME" >/dev/null; then
        echo "Group '$GROUPNAME' does not exist. Creating..."
        groupadd "$GROUPNAME"

        if [ $? -ne 0 ]; then
            echo "Error: failed to create group '$GROUPNAME'"
            exit 1
        fi
    fi
fi

if id "$USERNAME" >/dev/null 2>&1; then
    if [ -z "$GROUPNAME" ]; then
        echo "User '$USERNAME' already exists"
        exit 0
    fi

    if groups "$USERNAME" | grep -qw "$GROUPNAME"; then
        echo "User '$USERNAME' is already in group '$GROUPNAME'"
        exit 0
    fi

    usermod -aG "$GROUPNAME" "$USERNAME"

    if [ $? -eq 0 ]; then
        echo "Existing user '$USERNAME' added to group '$GROUPNAME'"
        exit 0
    else
        echo "Error: failed to add '$USERNAME' to group '$GROUPNAME'"
        exit 1
    fi
fi

if [ -n "$GROUPNAME" ]; then
    useradd -m -s /bin/bash -G "$GROUPNAME" "$USERNAME"
else
    useradd -m -s /bin/bash "$USERNAME"
fi

if [ $? -ne 0 ]; then
    echo "Error: failed to create user '$USERNAME'"
    exit 1
fi

passwd "$USERNAME"

if [ $? -ne 0 ]; then
    echo "Error: password setup failed for '$USERNAME'"
    exit 1
fi

if [ -n "$GROUPNAME" ]; then
    echo "User '$USERNAME' created and added to group '$GROUPNAME'"
else
    echo "User '$USERNAME' created successfully"
fi
