from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=409)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message=message, status_code=401)


class ForbiddenError(AppError):
    """Вошёл, но этот раздел ему не положен.

    Отдельно от 401 не ради чистоты кода, а ради поведения интерфейса. Фронт на
    401 считает, что сессия протухла, и уводит на страницу входа. Пока нехватка
    прав приходила тем же 401, работник цеха, набравший адрес закрытого раздела,
    получал форму входа — вводил тот же логин и снова оказывался на форме. По
    403 фронт показывает «Недостаточно прав» и оставляет человека в системе.
    """

    def __init__(self, message: str = "Недостаточно прав") -> None:
        super().__init__(message=message, status_code=403)
