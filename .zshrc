eval "$(dircolors -b ~/.dircolors)"
autoload -U colors && colors
typeset -A ZSH_HIGHLIGHT_STYLES

ZSH_HIGHLIGHT_STYLES[default]='fg=214'

ZSH_HIGHLIGHT_STYLES[command]='fg=208'
ZSH_HIGHLIGHT_STYLES[precommand]='fg=208'
ZSH_HIGHLIGHT_STYLES[arg0]='fg=208'

ZSH_HIGHLIGHT_STYLES[builtin]='fg=214'
ZSH_HIGHLIGHT_STYLES[function]='fg=215'
ZSH_HIGHLIGHT_STYLES[alias]='fg=214'
ZSH_HIGHLIGHT_STYLES[suffix-alias]='fg=214'

ZSH_HIGHLIGHT_STYLES[path]='fg=216'
ZSH_HIGHLIGHT_STYLES[globbing]='fg=215'
ZSH_HIGHLIGHT_STYLES[reserved-word]='fg=209'

ZSH_HIGHLIGHT_STYLES[unknown-token]='fg=166'
ZSH_HIGHLIGHT_STYLES[redirection]='fg=209'
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]='fg=214'
ZSH_HIGHLIGHT_STYLES[single-quoted-argument]='fg=214'
ZSH_HIGHLIGHT_STYLES[dollar-quoted-argument]='fg=215'

source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

HISTFILE=~/.zsh_history
HISTSIZE=200000
SAVEHIST=200000

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
alias grep='grep --color=auto'
alias history='cat ~/.zsh_history'
alias la='ls -a'
alias mc='micro'

bindkey '^[[1;5D' backward-word
bindkey '^[[1;5C' forward-word
bindkey '^H' backward-kill-word
bindkey '^[[3;5~' kill-word
bindkey '^[[3~' delete-char

PROMPT='%F{208}[%~]$ %f'
