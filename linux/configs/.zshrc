autoload -U colors && colors
autoload -Uz compinit && compinit

ZSH_COLOR_THEME="${ZSH_COLOR_THEME:-orange}"
ZSH_COLOR_THEME="violet"

if [[ "$ZSH_COLOR_THEME" == "violet" ]]; then
	eval "$(dircolors -b ~/.violet_dircolors)"
	source ~/Programming/Environment/linux/scripts/violet.zsh
else
	eval "$(dircolors -b ~/.orange_dircolors)"
	source ~/Programming/Environment/linux/scripts/orange.zsh
fi

if [ -e "/usr/share/zsh/plugins/" ]; then
	source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
	source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
else
	source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
	source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
fi

HISTFILE=~/.zsh_history
HISTSIZE=400000
SAVEHIST=400000

setopt SHARE_HISTORY
setopt INC_APPEND_HISTORY
setopt HIST_EXPIRE_DUPS_FIRST
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_SPACE
setopt HIST_REDUCE_BLANKS
setopt HIST_IGNORE_ALL_DUPS
setopt HIST_SAVE_NO_DUPS
setopt HIST_FIND_NO_DUPS

ZSH_AUTOSUGGEST_STRATEGY=(history completion)

alias ls='ls --color=auto'
alias la='ls -la'
alias grep='grep --color=auto'
alias history='cat ~/.zsh_history'
alias mcr='micro'
alias ffmpeg='ffmpeg -hide_banner'
alias ffprobe='ffprobe -hide_banner'
alias ffplay='ffplay -hide_banner'
alias pacman_upgrade='sudo pacman -Syu --noconfirm && yay -Syu --noconfirm' 
alias pacman_autoremove='sudo pacman -Rns $(pacman -Qdttq)'

bindkey '^[[1;5D' backward-word
bindkey '^[[1;5C' forward-word
bindkey '^H' backward-kill-word
bindkey '^[[3;5~' kill-word
bindkey '^[[3~' delete-char

export PATH=$PATH:/home/$(whoami)/.local/bin
eval "$(uv generate-shell-completion zsh)"
