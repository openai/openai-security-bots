class ValidationError(Exception):
    def __init__(self, field, issue):
        self.field = field
        self.issue = issue
        super().__init__(f"{field} {issue}")


def required(values, *fields):
    for f in fields:
        if f not in values:
            raise ValidationError(f, "required")
        if values[f] == "":
            raise ValidationError(f, "required")
