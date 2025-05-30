import requests

import requests
import json

# 1. Create a session object (equivalent to WebRequestSession)
session = requests.Session()
session.proxies = {
        "http": "http://127.0.0.1:4275",
        "https": "http://127.0.0.1:4275",
    }
# 2. Set User-Agent
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
})

# 4. Define URL, Headers, and Body for the POST request
url = "https://www.patreon.com/api/posts?fields[post]=post_type%2Cpost_metadata&include=drop&json-api-version=1.0&json-api-use-default-includes=false"

# Headers:
# - 'authority', 'method', 'path', 'scheme' are not actual HTTP headers you send.
#   They are metadata about the request. `requests` handles these.
# - 'Content-Type' is explicitly set.
# - 'User-Agent' is already set on the session.
# - We should only include actual HTTP headers that are sent to the server.
headers = {
    "authority": "www.patreon.com",  # Often handled by requests, but can be specified
    "accept": "*/*",
    "cookie": """patreon_device_id=6a029399-a9c4-447c-8b4d-0c5cf1afc73a; session_id=oFwl6H0TxEpUI5UMtLHShJg8ofEL6H4O3QmNo9v8Buw; patreon_locale_code=zh-CN; patreon_location_country_code=SG; patreon_locale_code=zh-CN; patreon_location_country_code=SG; _cfuvid=yLuRcPIGftqKmPyT8XY5vymgyD0BkMPG.nxTmwwpNOE-1748076943776-0.0.1.1-604800000; cf_clearance=n2pJp.ZshoZgE1DvPcvuOltMAFZw933o0NMsOnoyFVk-1748076958-1.2.1.1-bEJd8j4GHwiGsPbhsUV2zLPPG6lbaUDR8NjAEgfTd6hZh3.Vup6eZ1YOxBegt22gUew842poVCYBSgjOrKWvSy3DrJWdKxnGdG_VOKC1t_HO_KIS9Zc9EUOZyEG_RcTmJMHbFy42SJd1Y78zVpJlGwCUWkYV8QKAApvv7BotRWrOqlMKAc1ycuAKuyAMG0qocnXV_LNpnU8m9uFZNWaj5fxIeLW6rA7viZASkdT5eNL9d9.D6UZ7_hry58AtbUfh1rRaPn5Nf2tunA11ECigs2XZraGjau63V8QPZ4sKtpvPUN9.ImVWUAOCvakEj9ohieq189IXMvckrOIfDbMnaeILHwe9Ekpc0R1jXAjd78nxjsv_E3zVJgEOU2Am_0LA; __ssid=db047b5a7e33a630f095ac625f26bcd; __stripe_mid=5546ae01-0460-4dde-a626-28bc6786ae5cbe2838; __cf_bm=GptqPX3PT_fuznqmNu.uVZBnqwCBXWKnGJOrhyS4VnI-1748089185-1.0.1.1-ln4e0EKUzWMw3McYhyT3tJ5.NwQJMbssSG98oondtpLLZ2CI9_6vdvvlT6uh8LKO502IYtE47N2LWT1eD7t5_raM51aYPGWDMPbtRrRKHHAPZ0jCvRO9Ty_7MkAWqHir; analytics_session_id=3d7c329e-b7ec-4187-a237-6fc7055231ce""",
    "accept-encoding": "gzip, deflate, br, zstd",  # requests handles this automatically but specifying is fine
    "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "cache-control": "no-cache",
    "content-type": "application/vnd.api+json",  # Important: matches -ContentType
    "origin": "https://www.patreon.com",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://www.patreon.com/posts/new?postType=text_only",
    "sec-ch-ua": '"Chromium";v="136", "Brave";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-arch": '"x86"',
    "sec-ch-ua-bitness": '"64"',
    "sec-ch-ua-full-version-list": '"Chromium";v="136.0.0.0", "Brave";v="136.0.0.0", "Not.A/Brand";v="99.0.0.0"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-model": '""',  # Empty string
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-platform-version": '"10.0.0"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sec-gpc": "1",
    "x-csrf-signature": "9YrE7z4i5ahpJiCsq8ioItxEk6MiAt541MDalGsAi7Y"
}

# Update session headers with these specific request headers
# This merges them with the session's default User-Agent
session.headers.update(headers)

# Request Body:
# The PowerShell body is a JSON string.
# In Python, we can pass it as a string to `data` or as a dict to `json`.
# Since Content-Type is `application/vnd.api+json`, using `data` with the string is more direct.
# If we used `json=payload_dict`, requests would set Content-Type to `application/json` by default,
# which might not be what we want if the server is strict about `vnd.api+json`.
# So, we ensure our `headers` dictionary has the correct `content-type`.

payload_string = '{"data":{"type":"post","attributes":{"post_type":"text_only"}}}'
# Alternatively, as a Python dictionary (and then use `json.dumps(payload_dict)` or `json=payload_dict` in post)
# payload_dict = {
#     "data": {
#         "type": "post",
#         "attributes": {
#             "post_type": "text_only"
#         }
#     }
# }

# 5. Make the POST request
try:
    response = session.post(url, data=payload_string)  # `data` expects a string or bytes
    # If you had payload_dict, you could do:
    # response = session.post(url, json=payload_dict)
    # This would automatically set Content-Type to application/json,
    # but our headers already specify application/vnd.api+json, so data=payload_string is better.

    # 6. Process the response
    print(f"Status Code: {response.status_code}")

    # Try to print JSON response if available, otherwise text
    try:
        print("Response JSON:")
        print(json.dumps(response.json(), indent=2))
    except json.JSONDecodeError:
        print("Response Text:")
        print(response.text)

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")

