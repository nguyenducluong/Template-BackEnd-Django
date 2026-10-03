"""Service layer của app accounts (spec §51).

Cấu trúc: View → Serializer (validator) → Service (business logic).
View KHÔNG chứa logic xoay token / thu hồi phiên — logic đó nằm ở đây và
trong `libs/auth/refresh_tokens.py`.
"""