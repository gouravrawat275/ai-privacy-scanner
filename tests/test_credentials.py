from modules import credentials


def test_first_account_can_be_registered_without_existing_config(monkeypatch, tmp_path):
    config_path = tmp_path / "auth_config.yaml"
    monkeypatch.setattr(credentials, "CONFIG_PATH", str(config_path))

    config = credentials.load_or_init_config()
    assert config["credentials"]["usernames"] == {}

    username = credentials.register_user(
        config,
        "Test",
        "User",
        "test@example.com",
        "SecurePass1!",
        "SecurePass1!",
    )

    loaded_config = credentials.load_config()
    assert username in loaded_config["credentials"]["usernames"]