# API Reference

## Authentication

All requests require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <your-api-key>
```

Keys are issued per-environment. Production keys start with `pk_live_`, test keys with `pk_test_`.

## List Users

```
GET /v1/users
```

Returns a paginated list of users. Supports `?limit=` (default 25, max 100) and `?cursor=` for pagination.

**Response:**

```json
{
  "data": [
    {"id": "usr_abc123", "email": "alice@example.com", "created_at": "2026-01-15T08:30:00Z"}
  ],
  "has_more": true,
  "next_cursor": "cur_xyz789"
}
```

## Create User

```
POST /v1/users
```

**Request body:**

```json
{
  "email": "bob@example.com",
  "name": "Bob Smith",
  "role": "member"
}
```

**Response:** Returns the created user object with a `201` status code.

## Rate Limits

All endpoints are rate-limited to 100 requests per minute per API key. When exceeded, the API returns `429 Too Many Requests` with a `Retry-After` header.
