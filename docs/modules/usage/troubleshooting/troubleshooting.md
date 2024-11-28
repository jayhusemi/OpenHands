# 🚧 Troubleshooting

:::tip
OpenHands only supports Windows via WSL. Please be sure to run all commands inside your WSL terminal.
:::

## Common Issues
* [Launch docker client failed](#launch-docker-client-failed)
* [Sessions are not restored](#sessions-are-not-restored)

---
### Launch docker client failed

**Description**

When running OpenHands, the following error is seen:
```
Launch docker client failed. Please make sure you have installed docker and started docker desktop/daemon.
```

**Resolution**
Try these in order:
* Confirm `docker` is running on your system. You should be able to run `docker ps` in the terminal successfully.
* If using Docker Desktop, ensure `Settings > Advanced > Allow the default Docker socket to be used` is enabled.
* Depending on your configuration you may need `Settings > Resources > Network > Enable host networking` enabled in Docker Desktop.
* Reinstall Docker Desktop.

### Sessions are not restored

**Description**

With a standard installation, session data is stored in memory.
Currently, if OpenHands' service is restarted, previous sessions become
invalid (a new secret is generated) and thus not recoverable.

**Resolution**

* Change configuration to make sessions persistent by editing the `config.toml`
file (in OpenHands's root folder) by specifying a `file_store` and an
absolute `file_store_path`:

```toml
file_store="local"
file_store_path="/absolute/path/to/openhands/cache/directory"
```

* Add a fixed jwt secret in your .bashrc, like below, so that previous session id's
should stay accepted.

```bash
EXPORT JWT_SECRET=A_CONST_VALUE
```

---
