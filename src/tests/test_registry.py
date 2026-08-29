from martevi.providers import TranslatingProvider, build_registry


async def test_build_registry_has_all_seven_provider_ids(async_client):
    registry = build_registry(async_client)

    assert set(registry) == {
        "met",
        "aic",
        "cleveland",
        "harvard",
        "rijksmuseum",
        "smithsonian",
        "vam",
    }


async def test_each_entry_is_wrapped_in_translating_provider(async_client):
    registry = build_registry(async_client)

    assert all(isinstance(provider, TranslatingProvider) for provider in registry.values())
    assert all(provider.provider_id == provider_id for provider_id, provider in registry.items())
