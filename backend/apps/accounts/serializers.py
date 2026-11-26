from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Membership, User


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "phone", "preferred_language", "is_active", "password"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated):
        password = validated.pop("password", None)
        user = User(**validated)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated):
        password = validated.pop("password", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class MembershipSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "user_name", "location", "location_name", "role", "is_active"]
