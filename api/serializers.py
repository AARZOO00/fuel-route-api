from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        max_length=200,
        help_text="Starting location within the USA (e.g. 'New York, NY')"
    )
    end = serializers.CharField(
        max_length=200,
        help_text="Destination location within the USA (e.g. 'Los Angeles, CA')"
    )

    def validate_start(self, value):
        if not value.strip():
            raise serializers.ValidationError("Start location cannot be empty.")
        return value.strip()

    def validate_end(self, value):
        if not value.strip():
            raise serializers.ValidationError("End location cannot be empty.")
        return value.strip()

    def validate(self, data):
        if data.get('start', '').lower() == data.get('end', '').lower():
            raise serializers.ValidationError("Start and end locations must be different.")
        return data
