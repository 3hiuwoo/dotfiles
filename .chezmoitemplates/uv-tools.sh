# Install packages.uv_tools per user after uv itself. Requires note_failure.
# Tools stay on uv-managed Python, as dot_config/uv/uv.toml asks, even on the
# first apply before that file exists; system Python upgrades cannot break them.
# Skipped when uv is unavailable; one failed tool never stops the others.
{{ range .packages.uv_tools -}}
if ! commands_available{{ range .commands }} {{ . | quote }}{{ end }}; then
    if ! command -v uv >/dev/null 2>&1; then
        note_failure {{ printf "%s (uv unavailable)" .name | quote }}
    else
        printf 'Installing %s with uv tool.\n' {{ .name | quote }}
        uv tool install --managed-python {{ .name | quote }} </dev/null \
            || note_failure {{ .name | quote }}
    fi
fi
{{ end -}}
