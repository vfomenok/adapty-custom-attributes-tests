"""Tests for setting profile custom attributes: PATCH /api/v2/server-side-api/profile/.

Documented contract (https://adapty.io/docs/api-adapty/operations/updateProfile):
  * custom_attributes is a list of {"key", "value"} objects, at most 30 per profile;
  * key: string, at most 30 chars, only letters, digits, "-", "." and "_";
  * value: string (at most 50 chars) or float.
Behaviour the docs do not describe (deleting, duplicates, merging) is covered by tests
that pin down the observed behaviour; see README.md for details.
"""

import pytest

from tests.helpers import (
    MAX_ATTRIBUTES,
    MAX_KEY_LENGTH,
    MAX_VALUE_LENGTH,
    assert_validation_error,
    attrs,
    custom_attributes_of,
)


def fill_profile(client, profile, count=MAX_ATTRIBUTES):
    attributes = [{"key": f"attr_{i}", "value": f"value_{i}"} for i in range(count)]
    stored = custom_attributes_of(
        client.set_custom_attributes(attributes, customer_user_id=profile.customer_user_id)
    )
    assert len(stored) == count
    return stored


class TestSetAttributes:
    def test_set_string_attribute(self, client, profile):
        response = client.set_custom_attributes(
            attrs(plan="gold"), customer_user_id=profile.customer_user_id
        )

        assert custom_attributes_of(response) == {"plan": "gold"}

    @pytest.mark.parametrize("value", [1.5, 0.0, -2.5, 30.0, 1.2345678901234567e300])
    def test_set_float_attribute(self, client, profile, value):
        response = client.set_custom_attributes(
            attrs(score=value), customer_user_id=profile.customer_user_id
        )

        stored = custom_attributes_of(response)
        assert stored == {"score": value}
        assert isinstance(stored["score"], float)

    def test_numeric_string_stays_string(self, client, profile):
        response = client.set_custom_attributes(
            attrs(code="30"), customer_user_id=profile.customer_user_id
        )

        assert custom_attributes_of(response) == {"code": "30"}

    def test_set_several_attributes_in_one_request(self, client, profile):
        response = client.set_custom_attributes(
            attrs(plan="gold", score=9.5, city="Moscow"), customer_user_id=profile.customer_user_id
        )

        assert custom_attributes_of(response) == {"plan": "gold", "score": 9.5, "city": "Moscow"}

    def test_set_max_attributes_in_one_request(self, client, profile):
        fill_profile(client, profile, MAX_ATTRIBUTES)

    def test_attributes_are_persisted(self, client, profile):
        client.set_custom_attributes(
            attrs(plan="gold", score=1.5), customer_user_id=profile.customer_user_id
        )

        response = client.get_profile(customer_user_id=profile.customer_user_id)

        assert custom_attributes_of(response) == {"plan": "gold", "score": 1.5}

    def test_identify_profile_by_profile_id(self, client, profile):
        response = client.set_custom_attributes(attrs(plan="gold"), profile_id=profile.profile_id)

        assert custom_attributes_of(response) == {"plan": "gold"}
        stored = custom_attributes_of(client.get_profile(customer_user_id=profile.customer_user_id))
        assert stored == {"plan": "gold"}


class TestKeyValidation:
    @pytest.mark.parametrize(
        "key",
        [
            "a",
            "k" * MAX_KEY_LENGTH,
            "aZ09-_.",
            "UPPER",
            "1234",
            "-",
            "_",
            ".",
        ],
        ids=["one_char", "max_length", "all_allowed_chars", "upper", "digits", "dash", "underscore", "dot"],
    )
    def test_valid_key_is_accepted(self, client, profile, key):
        response = client.set_custom_attributes(
            [{"key": key, "value": "v"}], customer_user_id=profile.customer_user_id
        )

        assert custom_attributes_of(response) == {key: "v"}

    def test_key_longer_than_limit_is_rejected(self, client, profile):
        response = client.set_custom_attributes(
            [{"key": "k" * (MAX_KEY_LENGTH + 1), "value": "v"}],
            customer_user_id=profile.customer_user_id,
        )

        assert_validation_error(response, "custom_attributes.0.key", "max_length")

    @pytest.mark.parametrize(
        "key",
        ["", "a b", " a", "a\tb", "ключ", "a@b", "a/b", "a+b", "a:b", "a,b", "ä", "😀"],
        ids=["empty", "space", "leading_space", "tab", "cyrillic", "at", "slash", "plus", "colon", "comma", "umlaut", "emoji"],
    )
    def test_key_with_forbidden_chars_is_rejected(self, client, profile, key):
        response = client.set_custom_attributes(
            [{"key": key, "value": "v"}], customer_user_id=profile.customer_user_id
        )

        assert_validation_error(response, "custom_attributes.0.key", "regex")

    def test_missing_key_is_rejected(self, client, profile):
        response = client.set_custom_attributes(
            [{"value": "v"}], customer_user_id=profile.customer_user_id
        )

        assert_validation_error(response, "custom_attributes.0.key", "missing")

    def test_keys_are_case_sensitive(self, client, profile):
        response = client.set_custom_attributes(
            attrs(Plan="A", plan="b"), customer_user_id=profile.customer_user_id
        )

        assert custom_attributes_of(response) == {"Plan": "A", "plan": "b"}

    @pytest.mark.xfail(strict=True, reason="Known issue: a numeric key is silently converted to a string")
    def test_non_string_key_is_rejected(self, client, profile):
        response = client.set_custom_attributes(
            [{"key": 123, "value": "v"}], customer_user_id=profile.customer_user_id
        )

        assert_validation_error(response, "custom_attributes.0.key")


class TestValueValidation:
    @pytest.mark.parametrize(
        "value",
        ["x" * MAX_VALUE_LENGTH, "я" * MAX_VALUE_LENGTH, "Привет, мир! 👋", "  ", "a"],
        ids=["max_length_ascii", "max_length_cyrillic", "unicode", "whitespace_only", "one_char"],
    )
    def test_valid_string_value_is_accepted(self, client, profile, value):
        response = client.set_custom_attributes(
            attrs(field=value), customer_user_id=profile.customer_user_id
        )

        assert custom_attributes_of(response) == {"field": value}

    @pytest.mark.parametrize(
        "value",
        ["x" * (MAX_VALUE_LENGTH + 1), "я" * (MAX_VALUE_LENGTH + 1)],
        ids=["ascii", "cyrillic"],
    )
    def test_value_longer_than_limit_is_rejected(self, client, profile, value):
        response = client.set_custom_attributes(
            attrs(field=value), customer_user_id=profile.customer_user_id
        )

        assert_validation_error(response, "custom_attributes.0.value", "value_error")

    @pytest.mark.parametrize(
        "value",
        [True, False, {"a": 1}, ["a"]],
        ids=["true", "false", "object", "array"],
    )
    def test_value_of_unsupported_type_is_rejected(self, client, profile, value):
        response = client.set_custom_attributes(
            attrs(field=value), customer_user_id=profile.customer_user_id
        )

        assert_validation_error(response, "custom_attributes.0.value")

    @pytest.mark.xfail(
        strict=True,
        reason="Known issue: JSON integers (30) are rejected, only 30.0 passes. "
        "JS clients cannot send 30.0: JSON.stringify(30.0) === '30'",
    )
    @pytest.mark.parametrize("value", [0, 30, -1])
    def test_integer_value_is_accepted(self, client, profile, value):
        response = client.set_custom_attributes(
            attrs(count=value), customer_user_id=profile.customer_user_id
        )

        assert custom_attributes_of(response) == {"count": value}

    @pytest.mark.xfail(strict=True, reason="Known issue: a missing value causes HTTP 500 instead of 400")
    def test_missing_value_is_rejected(self, client, profile):
        response = client.set_custom_attributes(
            [{"key": "field"}], customer_user_id=profile.customer_user_id
        )

        assert_validation_error(response, "custom_attributes.0.value")


class TestPayloadValidation:
    def test_more_than_max_attributes_in_one_request_is_rejected(self, client, profile):
        attributes = [{"key": f"attr_{i}", "value": i + 0.5} for i in range(MAX_ATTRIBUTES + 1)]

        response = client.set_custom_attributes(attributes, customer_user_id=profile.customer_user_id)

        assert_validation_error(response, "custom_attributes", "max_items")

    @pytest.mark.parametrize("payload", [{"plan": "gold"}, "plan", 1], ids=["object", "string", "number"])
    def test_custom_attributes_must_be_list(self, client, profile, payload):
        response = client.set_custom_attributes(payload, customer_user_id=profile.customer_user_id)

        assert_validation_error(response, "custom_attributes")

    def test_custom_attributes_null_is_rejected(self, client, profile):
        response = client.set_custom_attributes(None, customer_user_id=profile.customer_user_id)

        assert_validation_error(response, "custom_attributes")

    def test_error_points_to_invalid_item(self, client, profile):
        attributes = [{"key": "ok", "value": "v"}, {"key": "bad key", "value": "v"}]

        response = client.set_custom_attributes(attributes, customer_user_id=profile.customer_user_id)

        assert_validation_error(response, "custom_attributes.1.key")

    def test_invalid_request_saves_nothing(self, client, profile):
        client.set_custom_attributes(attrs(existing="old"), customer_user_id=profile.customer_user_id)
        attributes = attrs(existing="new", added="v") + [{"key": "bad key", "value": "v"}]

        response = client.set_custom_attributes(attributes, customer_user_id=profile.customer_user_id)

        assert response.status_code == 400
        stored = custom_attributes_of(client.get_profile(customer_user_id=profile.customer_user_id))
        assert stored == {"existing": "old"}


class TestUpdateAndDelete:
    def test_new_attributes_are_merged_with_existing(self, client, profile):
        client.set_custom_attributes(attrs(plan="gold"), customer_user_id=profile.customer_user_id)

        response = client.set_custom_attributes(
            attrs(city="Moscow"), customer_user_id=profile.customer_user_id
        )

        assert custom_attributes_of(response) == {"plan": "gold", "city": "Moscow"}

    @pytest.mark.parametrize(
        "old, new",
        [("gold", "silver"), ("gold", 2.5), (2.5, "gold"), (1.5, 2.5)],
        ids=["str_to_str", "str_to_float", "float_to_str", "float_to_float"],
    )
    def test_existing_attribute_is_overwritten(self, client, profile, old, new):
        client.set_custom_attributes(attrs(field=old, other="keep"), customer_user_id=profile.customer_user_id)

        response = client.set_custom_attributes(attrs(field=new), customer_user_id=profile.customer_user_id)

        assert custom_attributes_of(response) == {"field": new, "other": "keep"}

    def test_null_value_deletes_attribute(self, client, profile):
        client.set_custom_attributes(attrs(plan="gold", city="Moscow"), customer_user_id=profile.customer_user_id)

        response = client.set_custom_attributes(attrs(city=None), customer_user_id=profile.customer_user_id)

        assert custom_attributes_of(response) == {"plan": "gold"}
        stored = custom_attributes_of(client.get_profile(customer_user_id=profile.customer_user_id))
        assert stored == {"plan": "gold"}

    def test_empty_string_value_deletes_attribute(self, client, profile):
        # Not documented; pins the observed behaviour: "" works like null.
        client.set_custom_attributes(attrs(plan="gold", city="Moscow"), customer_user_id=profile.customer_user_id)

        response = client.set_custom_attributes(attrs(city=""), customer_user_id=profile.customer_user_id)

        assert custom_attributes_of(response) == {"plan": "gold"}

    def test_null_for_unknown_key_changes_nothing(self, client, profile):
        client.set_custom_attributes(attrs(plan="gold"), customer_user_id=profile.customer_user_id)

        response = client.set_custom_attributes(attrs(unknown=None), customer_user_id=profile.customer_user_id)

        assert custom_attributes_of(response) == {"plan": "gold"}

    def test_empty_list_changes_nothing(self, client, profile):
        client.set_custom_attributes(attrs(plan="gold"), customer_user_id=profile.customer_user_id)

        response = client.set_custom_attributes([], customer_user_id=profile.customer_user_id)

        assert custom_attributes_of(response) == {"plan": "gold"}

    def test_request_without_custom_attributes_changes_nothing(self, client, profile):
        client.set_custom_attributes(attrs(plan="gold"), customer_user_id=profile.customer_user_id)

        response = client.set_custom_attributes(customer_user_id=profile.customer_user_id)

        assert custom_attributes_of(response) == {"plan": "gold"}

    def test_duplicate_keys_last_value_wins(self, client, profile):
        attributes = [{"key": "plan", "value": "gold"}, {"key": "plan", "value": "silver"}]

        response = client.set_custom_attributes(attributes, customer_user_id=profile.customer_user_id)

        assert custom_attributes_of(response) == {"plan": "silver"}

    def test_delete_and_add_in_one_request(self, client, profile):
        client.set_custom_attributes(attrs(old="v"), customer_user_id=profile.customer_user_id)

        response = client.set_custom_attributes(
            attrs(old=None, new="v"), customer_user_id=profile.customer_user_id
        )

        assert custom_attributes_of(response) == {"new": "v"}


class TestProfileLimit:
    def test_existing_attribute_can_be_updated_when_profile_is_full(self, client, profile):
        fill_profile(client, profile)

        response = client.set_custom_attributes(
            attrs(attr_0="updated"), customer_user_id=profile.customer_user_id
        )

        stored = custom_attributes_of(response)
        assert len(stored) == MAX_ATTRIBUTES
        assert stored["attr_0"] == "updated"

    def test_freed_slot_can_be_reused(self, client, profile):
        fill_profile(client, profile)

        response = client.set_custom_attributes(
            attrs(attr_0=None, replacement="v"), customer_user_id=profile.customer_user_id
        )

        stored = custom_attributes_of(response)
        assert len(stored) == MAX_ATTRIBUTES
        assert "attr_0" not in stored
        assert stored["replacement"] == "v"

    def test_profile_never_exceeds_limit(self, client, profile):
        fill_profile(client, profile)

        client.set_custom_attributes(attrs(extra="v"), customer_user_id=profile.customer_user_id)

        stored = custom_attributes_of(client.get_profile(customer_user_id=profile.customer_user_id))
        assert len(stored) == MAX_ATTRIBUTES
        assert "extra" not in stored

    @pytest.mark.xfail(
        strict=True,
        reason="Known issue: attributes over the profile limit are silently dropped with HTTP 200",
    )
    def test_exceeding_profile_limit_returns_error(self, client, profile):
        fill_profile(client, profile)

        response = client.set_custom_attributes(attrs(extra="v"), customer_user_id=profile.customer_user_id)

        assert response.status_code == 400, response.text


class TestAuthAndProfileResolution:
    def test_invalid_api_key_is_rejected(self, client, profile):
        response = client.update_profile(
            {"custom_attributes": attrs(plan="gold")},
            headers={"Authorization": "Api-Key secret_live_invalid"},
            customer_user_id=profile.customer_user_id,
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "not_authenticated"
        assert custom_attributes_of(client.get_profile(customer_user_id=profile.customer_user_id)) == {}

    def test_missing_api_key_is_rejected(self, client, profile):
        # Docs promise 401; the API actually answers 403 with a plain-text body.
        response = client.update_profile(
            {"custom_attributes": attrs(plan="gold")},
            headers={"Authorization": ""},
            customer_user_id=profile.customer_user_id,
        )

        assert response.status_code in (401, 403)
        assert custom_attributes_of(client.get_profile(customer_user_id=profile.customer_user_id)) == {}

    def test_unknown_profile_returns_404(self, client):
        response = client.set_custom_attributes(
            attrs(plan="gold"), customer_user_id="autotest-does-not-exist-0000"
        )

        assert response.status_code == 404
        assert response.json()["error_code"] == "profile_does_not_exist"

    def test_deleted_profile_returns_404(self, client, profile):
        client.delete_profile(customer_user_id=profile.customer_user_id)

        response = client.set_custom_attributes(attrs(plan="gold"), customer_user_id=profile.customer_user_id)

        assert response.status_code == 404

    def test_missing_profile_identifier_is_rejected(self, client):
        response = client.set_custom_attributes(attrs(plan="gold"))

        assert response.status_code == 400
        assert response.json()["error_code"] == "value_error"

    def test_malformed_profile_id_is_rejected(self, client):
        response = client.set_custom_attributes(attrs(plan="gold"), profile_id="not-a-uuid")

        assert_validation_error(response, "profile_id")
