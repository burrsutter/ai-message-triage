# zsh completion for the repository's ./send.sh sample-message argument.

_message_triage_send() {
  if (( CURRENT != 2 )); then
    return
  fi

  local command_path="${words[1]}"
  local -a samples

  if [[ ! -x "${command_path}" ]]; then
    return
  fi

  samples=("${(@f)$("${command_path}" --list 2>/dev/null)}")
  _describe 'sample message' samples
}

compdef _message_triage_send send.sh ./send.sh
