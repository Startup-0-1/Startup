from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User, PatientProfile, DoctorProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role", "created_at"]


class PatientSignupSerializer(serializers.Serializer):
    # user fields
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, min_length=6)

    # profile fields
    full_name = serializers.CharField(max_length=255)
    date_of_birth = serializers.CharField(max_length=50)
    gender = serializers.CharField(max_length=50)
    contact_number = serializers.CharField(max_length=50)
    address = serializers.CharField()
    emergency_contact = serializers.CharField(max_length=255, required=False, allow_blank=True)
    insurance_provider = serializers.CharField(max_length=255, required=False, allow_blank=True)
    insurance_policy_number = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError("Passwords do not match.")
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError("Email is already registered.")
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("password_confirm")

        email = validated_data.pop("email")

        user = User.objects.create_user(email=email, password=password, role="patient")
        PatientProfile.objects.create(user=user, **validated_data)
        return user


class DoctorSignupSerializer(serializers.Serializer):
    # user fields
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, min_length=6)

    # profile fields
    full_name = serializers.CharField(max_length=255)
    specialization = serializers.CharField(max_length=255)
    license_number = serializers.CharField(max_length=255)
    years_of_experience = serializers.IntegerField()
    contact_number = serializers.CharField(max_length=50)
    clinic_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    clinic_address = serializers.CharField(required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError("Passwords do not match.")
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError("Email is already registered.")
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("password_confirm")

        email = validated_data.pop("email")

        user = User.objects.create_user(email=email, password=password, role="doctor")
        DoctorProfile.objects.create(user=user, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        attrs["user"] = user
        return attrs
