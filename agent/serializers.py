from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000, trim_whitespace=True)
    thread_id = serializers.CharField(max_length=64)
