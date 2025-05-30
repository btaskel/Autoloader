import json
import os
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options

# --- 用户配置 ---
CSRF_TOKEN = "9YrE7z4i5ahpJiCsq8ioItxEk6MiAt541MDalGsAi7Y"  # 从HAR或浏览器中获取

# 请将下方替换为您从浏览器开发者工具中复制的完整Cookie字符串
# (例如，在Network选项卡中，找到对patreon.com的请求，复制Request Headers中的Cookie值)
RAW_COOKIE_STRING = (
    "__cf_bm=4ogZFwB144f5tU6z7wLraV4_UuhKf7gro3rjI42W3Oo-1747385724-1.0.1.1-h6wBfOLfm8azo5zMoe76poXLZ6HGFBKc3ljX.aDa.4zWGLkBmLbF74du1KM95tIAzDq4fybCMq3sLkM4dmzK5Ss9fjkI2OKNaUYbtPklCmegO087ndV5ATgVZmaijdXe; "
    "_cfuvid=wfYdT2SHxnqk9ZHqpmiGeK2GpOsyf4JLPwPOjz3ITmM-1747385724924-0.0.1.1-604800000; "
    "patreon_device_id=1c19a460-99e3-479c-9126-b1a92e7a8be7; "
    "analytics_session_id=89553b91-141c-42c0-8ce0-aa9bc6daa45b; "
    "cf_clearance=nxSE9Ks0EyIi_1HUXmTPsHpbXHQeiyhd6YBlWi4Krk8-1747385767-1.2.1.1-f3TyXxCf6de9ko7uJbZFeINU8o_8WFhM1JeH5j.8z4MMttuVEaOLvER5rSFKoFJ0C3f6JXgaedv6UmlG.c0rO.0iMFgdIatTYEuNoNMy89eBZ3qaaY3NF9GsLkrNYl2cMiaUfLBRZlB2GSLnVBOJFARvaTLUzsGbTte9KMWysORkBlXxsfzifRdIEdgPyKsJVT.ZRT.a1krK7Mbq.rkj4R8BoRgGayynxyKzUE3JefSXeS9CUJvl2Y8KV1ZmkdZ.umVb2G5vto6uan1qvjDLCh1votEoH1aEdKJwVYItcPwNOSCbkZmwDfu6J2mqxlCWKgJDx0pSmIpR4oOxN3g1mWpqVrg7GAJw6VKiX3hBo3QUIMe1qdsQsAQxeF6pI.qY; "
    "g_state={\"i_l\":0}; "
    "session_id=MtJ4_VjHncWpNFq8rNCcsMzreH8Xmfn4k5aPcLKoCQU; "
    "patreon_locale_code=zh-CN; "  # 注意：这个cookie在您的示例中出现了两次
    "patreon_location_country_code=SG; "  # 这个cookie也在您的示例中出现了两次
    "can_see_nsfw=1; "
    "__ssid=de98594861b65f23a04ce855ee2a054"  # 最后的cookie不需要分号
    # 如果您的cookie字符串是从浏览器复制的，末尾可能没有分号，这是正常的
)

IMAGE_PATH = "testdata/test.jpg"
POST_TITLE = "这是我的新图片帖子！(Selenium)"
POST_CONTENT_HTML = "<p>大家好，看看这张通过Selenium脚本发布的新图片吧！</p><p>希望你们喜欢！</p>"
TARGET_ACCESS_RULE_ID = "55130353"
CAMPAIGN_ID = "10302787"

PROXY_ADDRESS = "http://127.0.0.1:4275"


# --- Selenium 设置 (init_driver 函数更新) ---
def init_driver():
    chrome_options = Options()
    # PROXY_SERVER = {
    #     "http": PROXY_ADDRESS,
    #     "https": PROXY_ADDRESS
    # }  # "http://127.0.0.1:4275" # 从你之前的代码中保留
    #
    # os.environ['HTTP_PROXY'] = PROXY_ADDRESS
    # os.environ['HTTPS_PROXY'] = PROXY_ADDRESS  # HTTPS请求也通过HTTP代理（如果代理支持）

    chrome_options.add_argument(f'--proxy-server={PROXY_ADDRESS}')
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # 从HAR中获取的User-Agent
    chrome_options.add_argument(
        f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)

    # 必须先导航到目标域才能设置cookie
    driver.get("https://www.patreon.com/login")  # 或者任何 patreon.com 页面
    time.sleep(2)  # 等待页面基本加载

    if RAW_COOKIE_STRING:
        parsed_cookies = []
        # RAW_COOKIE_STRING 是一个由分号分隔的cookie键值对字符串
        cookie_pairs = RAW_COOKIE_STRING.strip().split(';')
        for pair_str in cookie_pairs:
            pair_str = pair_str.strip()
            if not pair_str:  # 跳过因额外分号产生的空字符串
                continue

            if '=' in pair_str:
                name, value = pair_str.split('=', 1)
                cookie_dict = {
                    'name': name,
                    'value': value,
                    'domain': '.patreon.com',  # 应用于主域及其子域
                    'path': '/',  # 通常的默认路径
                    'secure': True,  # 假设所有Patreon的cookie都是Secure
                }
                # Cloudflare的特定cookie通常是HttpOnly
                if name in ["__cf_bm", "cf_clearance", "_cfuvid", "__ssid"]:  # __ssid也可能是
                    cookie_dict['httpOnly'] = True
                else:
                    cookie_dict['httpOnly'] = False  # 其他Patreon应用cookie可能不是HttpOnly

                # 对于 session_id, HttpOnly 通常为 True
                if name == "session_id":
                    cookie_dict['httpOnly'] = True

                parsed_cookies.append(cookie_dict)
            else:
                print(f"警告: Cookie格式不正确，已跳过: '{pair_str}'")

        for cookie in parsed_cookies:
            try:
                # 为了确保能设置成功，特别是HttpOnly的cookie，有时先删除同名cookie有帮助
                # 但对于新session，通常不需要。如果遇到问题可以尝试取消注释下一行。
                # driver.delete_cookie(cookie['name'])
                driver.add_cookie(cookie)
            except WebDriverException as e:
                # 捕获更具体的Selenium异常
                if "invalid cookie domain" in str(e).lower():
                    print(f"警告: Cookie '{cookie['name']}' 的域 '.patreon.com' 可能无效。尝试使用 'www.patreon.com'。")
                    cookie_alt = cookie.copy()
                    cookie_alt['domain'] = 'www.patreon.com'
                    try:
                        driver.add_cookie(cookie_alt)
                    except Exception as e_alt:
                        print(f"使用 'www.patreon.com' 添加cookie '{cookie['name']}' 仍失败: {e_alt}")
                elif "unable to set cookie" in str(e).lower() and cookie.get('httpOnly'):
                    print(f"警告: 设置HttpOnly cookie '{cookie['name']}' 可能有限制。尝试不设置HttpOnly。")
                    cookie_no_http = cookie.copy()
                    del cookie_no_http['httpOnly']  # 移除httpOnly属性再试
                    try:
                        driver.add_cookie(cookie_no_http)
                    except Exception as e_no_http:
                        print(f"不设置HttpOnly添加cookie '{cookie['name']}' 仍失败: {e_no_http}")
                else:
                    print(f"添加cookie '{cookie['name']}' 失败: {e}")
            except Exception as e_general:  # 其他未知错误
                print(f"添加cookie '{cookie['name']}' 时发生一般错误: {e_general}")

    # 再次访问目标页面或首页，以使cookies生效
    target_page = f"https://www.patreon.com/c/{CAMPAIGN_ID}/posts" if CAMPAIGN_ID else "https://www.patreon.com/home"
    print(f"导航到 {target_page} 以应用cookies...")
    driver.get(target_page)
    driver.set_page_load_timeout(25)  # 增加超时
    try:
        time.sleep(5)  # 等待页面加载和可能的JS初始化
    except TimeoutException:
        print("页面加载超时，但脚本将继续...")

    # 验证一下关键cookie是否设置成功
    print("当前域的Cookies:")
    current_cookies = driver.get_cookies()
    found_session = False
    found_cf_clearance = False
    for c in current_cookies:
        # print(f" - {c.get('name')}: {c.get('domain')}") # 调试用
        if c.get('name') == 'session_id':
            found_session = True
        if c.get('name') == 'cf_clearance':
            found_cf_clearance = True
    if found_session:
        print("  session_id cookie已设置。")
    else:
        print("  警告: session_id cookie 未找到！认证可能失败。")
    if found_cf_clearance:
        print("  cf_clearance cookie已设置。")
    else:
        print("  警告: cf_clearance cookie 未找到！Cloudflare验证可能失败。")

    return driver


# --- API 请求辅助函数 (通过Selenium执行JS fetch) ---
def patreon_api_request(driver, url, method='GET', payload=None, extra_headers=None, is_s3_upload=False,
                        file_bytes=None, s3_form_data=None, file_name_s3=None, file_mime_type=None):
    headers = {
        'Accept': 'application/vnd.api+json, */*',  # 确保API JSON优先，但S3可能不同
        'X-CSRF-Signature': CSRF_TOKEN,
        'Origin': 'https://www.patreon.com',
        # Referer 会根据具体请求设置
    }
    if not is_s3_upload:  # 大部分API请求
        headers['Content-Type'] = 'application/vnd.api+json'

    if extra_headers:
        headers.update(extra_headers)

    if is_s3_upload:
        # S3上传使用 FormData，不需要 Content-Type 和 CSRF 在 headers 对象里
        # FormData 会自动设置 multipart/form-data
        # file_bytes 需要是 list of numbers (byte values)
        js_script = """
        const url = arguments[0];
        const s3FormData = arguments[1];
        const fileBytes = arguments[2];
        const fileName = arguments[3];
        const fileMimeType = arguments[4];
        const callback = arguments[5];

        const formData = new FormData();
        for (const key in s3FormData) {
            formData.append(key, s3FormData[key]);
        }
        // 确保文件名正确，S3的'file'字段通常是最后一个
        formData.append('file', new Blob([new Uint8Array(fileBytes)], {type: fileMimeType}), fileName);

        fetch(url, {
            method: 'POST',
            body: formData,
            // S3预签名POST通常不需要额外的认证头，因为认证信息在表单字段中
        })
        .then(response => {
            if (!response.ok && response.status !== 204 && response.status !== 201) { // S3成功通常是204或201
                return response.text().then(text => Promise.reject(`S3 Upload HTTP error ${response.status}: ${text}`));
            }
            return { status: response.status, text: response.status === 204 ? "Success (204)" : response.text() };
        })
        .then(data => callback(data))
        .catch(error => callback({error: error.toString()}));
        """
        return driver.execute_async_script(js_script, url, s3_form_data, list(file_bytes), file_name_s3, file_mime_type)

    else:  # 普通 JSON API 请求
        body_str = json.dumps(payload) if payload else None
        js_script = """
        const url = arguments[0];
        const method = arguments[1];
        const headers = arguments[2];
        const body = arguments[3];
        const callback = arguments[4];

        fetch(url, {
            method: method,
            headers: headers,
            body: body
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => Promise.reject(`HTTP error ${response.status}: ${text}`));
            }
            // 如果预期空响应或非JSON响应
            if (response.status === 204) return { status: 204, data: null };
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/vnd.api+json") !== -1) {
                 return response.json().then(data => ({ status: response.status, data: data, headers: Object.fromEntries(response.headers.entries()) }));
            }
            return response.text().then(text => ({ status: response.status, data: text, headers: Object.fromEntries(response.headers.entries()) }));
        })
        .then(data => callback(data))
        .catch(error => callback({error: error.toString()}));
        """
        return driver.execute_async_script(js_script, url, method, headers, body_str)


def main():
    driver = init_driver()
    post_id = None
    media_id = None
    media_object_from_api = None  # 保存从 /api/media 获取的完整媒体对象

    try:
        file_name = os.path.basename(IMAGE_PATH)
        file_size = os.path.getsize(IMAGE_PATH)
        with open(IMAGE_PATH, 'rb') as f:
            image_file_bytes = f.read()

        # 探测图片MIME类型
        # 简单探测，对于更复杂的场景可能需要python-magic库
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext == '.png':
            image_mime_type = 'image/png'
        elif file_ext in ['.jpg', '.jpeg']:
            image_mime_type = 'image/jpeg'
        elif file_ext == '.gif':
            image_mime_type = 'image/gif'
        else:
            print(f"警告: 未知的图片MIME类型 '{file_ext}', 默认为 'application/octet-stream'")
            image_mime_type = 'application/octet-stream'

        # 1. 创建草稿帖子 (初始为 text_only，后面会改)
        print("1. 正在创建草稿帖子...")
        create_post_url = "https://www.patreon.com/api/posts?fields[post]=post_type%2Cpost_metadata&include=drop&json-api-version=1.0&json-api-use-default-includes=false"
        create_post_payload = {"data": {"type": "post", "attributes": {"post_type": "text_only"}}}
        # Referer 来自HAR page_1 的 https://www.patreon.com/posts/new?postType=text_only，但用 creator page 应该也行
        referer_create_post = f"https://www.patreon.com/c/{CAMPAIGN_ID}/posts" if CAMPAIGN_ID else "https://www.patreon.com/posts/new"

        response_data = patreon_api_request(driver, create_post_url, 'POST', create_post_payload,
                                            {'Referer': referer_create_post})
        if 'error' in response_data:
            raise Exception(f"创建草稿帖子失败: {response_data['error']}")

        post_id = response_data['data']['data']['id']
        print(f"   草稿帖子创建成功, Post ID: {post_id}")
        time.sleep(1)

        # 2. 注册媒体文件
        print(f"2. 正在为 Post ID {post_id} 注册媒体文件 {file_name}...")
        register_media_url = "https://www.patreon.com/api/media?json-api-version=1.0&json-api-use-default-includes=false&include=[]"
        register_media_payload = {
            "data": {
                "type": "media",
                "attributes": {
                    "state": "pending_upload",
                    "owner_id": post_id,
                    "owner_type": "post",
                    "owner_relationship": "main",  # HAR中是main, 有时候可能是images
                    "file_name": file_name,
                    "size_bytes": file_size,
                    "media_type": "image"
                }
            }
        }
        referer_media = f"https://www.patreon.com/posts/{post_id}/edit"
        response_data = patreon_api_request(driver, register_media_url, 'POST', register_media_payload,
                                            {'Referer': referer_media})
        if 'error' in response_data:
            raise Exception(f"注册媒体文件失败: {response_data['error']}")

        media_data_attributes = response_data['data']['data']['attributes']
        media_id = response_data['data']['data']['id']
        media_object_from_api = response_data['data']['data']  # 保存整个对象
        s3_upload_url = media_data_attributes['upload_url']
        s3_form_data = media_data_attributes['upload_parameters']
        print(f"   媒体文件注册成功, Media ID: {media_id}")
        time.sleep(1)

        # 3. 上传到S3
        print(f"3. 正在上传图片到S3: {s3_upload_url} ...")
        s3_response = patreon_api_request(driver, s3_upload_url, is_s3_upload=True,
                                          file_bytes=image_file_bytes, s3_form_data=s3_form_data,
                                          file_name_s3=file_name, file_mime_type=image_mime_type)
        if s3_response and 'error' in s3_response:  # execute_async_script returns None on success if no callback value
            raise Exception(f"S3上传失败: {s3_response['error']}")
        # S3 成功通常是 201 或 204, 并且没有body，或者XML body
        # 我们在JS中处理了状态码，如果JS没报错，就认为成功
        print(f"   S3上传成功 (JS认为状态码OK)")
        time.sleep(3)  # 等待S3处理和Patreon后台同步

        # 4. 更新帖子类型为 image_file
        print(f"4. 正在更新 Post ID {post_id} 类型为 image_file...")
        update_post_type_url = f"https://www.patreon.com/api/posts/{post_id}?fields[post]=post_type&json-api-version=1.0&json-api-use-default-includes=false&include=[]"
        update_post_type_payload = {
            "data": {"attributes": {"post_type": "image_file"}},  # HAR中只有 post_type，但为了安全，也可以用attributes
            "meta": {"auto_save": True}  # HAR 中没有 meta，但通常 autosave 为 true
        }
        response_data = patreon_api_request(driver, update_post_type_url, 'PATCH', update_post_type_payload,
                                            {'Referer': referer_media})
        if 'error' in response_data:
            raise Exception(f"更新帖子类型失败: {response_data['error']}")
        print("   帖子类型更新成功。")
        time.sleep(1)

        # 5. 关联图片到帖子
        print(f"5. 正在关联 Media ID {media_id} 到 Post ID {post_id}...")
        link_image_url = f"https://www.patreon.com/api/posts/{post_id}/relationships/images?json-api-version=1.0&json-api-use-default-includes=false&include=[]"

        # 使用从 /api/media 响应中获取的完整媒体对象结构，并确保有type和id
        media_object_for_linking = {
            "type": "media",
            "id": media_id,
            # **media_object_from_api # 展开整个对象, 但确保 type 和 id 优先
        }
        # HAR中的data是一个列表，包含完整的媒体对象，但至少需要 type 和 id
        # "data":[{"type":"media","id":"471898429","createdAt":"...", ...}]
        # 这里我们简化为只发送必要的type和id，如果Patreon需要完整对象，则需要填充media_object_from_api
        link_image_payload = {"data": [media_object_for_linking]}

        response_data = patreon_api_request(driver, link_image_url, 'PATCH', link_image_payload,
                                            {'Referer': referer_media})
        # 关联成功通常返回 204 No Content
        if 'error' in response_data:
            # 检查是否是因为204 No Content（这其实是成功）
            if not (response_data.get('status') == 204 and response_data.get('data') is None):
                raise Exception(f"关联图片失败: {response_data['error']}")
        print("   图片关联成功。")
        time.sleep(1)

        # 6. (可选) 内容检查 - HAR中有，但可能不是严格必须的。为了模拟完整流程，我们加上。
        print("6. 正在进行内容合规性检查 (模拟)...")
        content_check_url = "https://www.patreon.com/api/content/check?json-api-version=1.0&json-api-use-default-includes=false&include=[]"

        # 检查标题
        title_check_payload = {"data": {"text": f"{POST_TITLE} null"}}  # 模拟HAR
        response_data = patreon_api_request(driver, content_check_url, 'POST', title_check_payload,
                                            {'Referer': referer_media})
        if 'error' in response_data:
            print(f"   警告: 标题检查可能失败或返回非预期格式: {response_data['error']}")
        else:
            print(f"   标题检查响应: {response_data.get('data', {}).get('data', {}).get('attributes', {})}")
        time.sleep(0.5)

        # 检查内容
        content_check_payload = {"data": {"text": f"{POST_TITLE} {POST_CONTENT_HTML}"}}  # 模拟HAR
        response_data = patreon_api_request(driver, content_check_url, 'POST', content_check_payload,
                                            {'Referer': referer_media})
        if 'error' in response_data:
            print(f"   警告: 内容检查可能失败或返回非预期格式: {response_data['error']}")
        else:
            print(f"   内容检查响应: {response_data.get('data', {}).get('data', {}).get('attributes', {})}")
        time.sleep(1)

        # 7. 最终发布/更新帖子 (设置标题、内容、等级、图片顺序等)
        print(f"7. 正在发布 Post ID {post_id}...")
        # 这个URL的参数列表非常长，从HAR中复制
        final_publish_url = f"https://www.patreon.com/api/posts/{post_id}?include=access_rules.tier.null%2Cattachments.null%2Cattachments_media%2Ccampaign.access_rules.tier.null%2Ccampaign.earnings_visibility%2Ccampaign.is_nsfw%2Cpoll%2Cpoll.choices%2Cuser.null%2Cuser_defined_tags.null%2Cimages.null%2Caudio%2Cvideo%2Cmoderator_actions%2Ccan_ask_pls_question_via_zendesk%2Caudio_preview.null%2Ccollections%2Cshows%2Ccontent_locks.null%2Cdrop%2Ccontent_unlock_options.product_variant.null%2Ccontent_unlock_options.reward.null%2Cpublish_channels%2Cparent_highlight_post%2Cpodcast%2Crss_synced_feed%2Ccustom_thumbnail_media.null%2Ccollaborations&fields[post]=allow_preview_in_rss%2Ccategory%2Ccents_pledged_at_creation%2Cchange_visibility_at%2Ccomment_count%2Ccomments_write_access_level%2Ccontent%2Ccreated_at%2Ccurrent_user_can_delete%2Ccurrent_user_can_view%2Ccurrent_user_has_liked%2Cdeleted_at%2Cedit_url%2Cedited_at%2Cembed%2Cimage%2Cis_automated_monthly_charge%2Cis_paid%2Cis_highlight%2Cis_preview_blurred%2Clike_count%2Cmin_cents_pledged_to_view%2Cnew_post_email_type%2Cnum_pushable_users%2Cpatreon_url%2Cpatron_count%2Cpledge_url%2Cpost_file%2Cpost_metadata%2Cpost_type%2Cpreview_asset_type%2Cpublished_at%2Cscheduled_for%2Cteaser_text%2Cthumbnail%2Cthumbnail_position%2Ctitle%2Curl%2Cwas_posted_by_campaign_owner%2Cvideo_external_upload_url%2Cmoderation_status%2Cvideo_preview_start_ms%2Cvideo_preview_end_ms%2Cpost_level_suspension_removal_date%2Cpls_one_liners_by_category%2Ccan_ask_pls_question_via_zendesk%2Ccurrent_user_has_post_visibility_locked&fields[access_rule]=access_rule_type%2Camount_cents&fields[reward]=title%2Camount_cents%2Ccurrency%2Cpatron_count%2Cid%2Cpublished%2Cis_free_tier&fields[campaign]=can_create_paid_posts%2Ccomments_access_level%2Cis_nsfw%2Coffers_free_membership%2Cdefault_post_price_cents&fields[media]=id%2Cimage_urls%2Cdisplay%2Cdownload_url%2Cmetadata%2Cclosed_captions_enabled%2Cclosed_captions%2Csize_bytes%2Cfile_name%2Cstate%2Cmedia_type&fields[content-unlock-option]=content_unlock_type%2Creward_benefit_categories&fields[product-variant]=price_cents%2Ccurrency_code%2Cis_hidden%2Cpublished_at_datetime%2Corders_count&fields[podcast]=rss_published_at&fields[rss-synced-feed]=rss_url&fields[shows]=id%2Ctitle%2Cdescription%2Cthumbnail&fields[post-collaboration]=status%2Ccollaborator_campaign_id%2Ccollaborator_name&json-api-version=1.0&json-api-use-default-includes=false"

        publish_payload = {
            "data": {
                "type": "post",
                "id": post_id,  # 确保ID在这里
                "attributes": {
                    "title": POST_TITLE,
                    "content": POST_CONTENT_HTML,
                    "post_type": "image_file",
                    "is_paid": False,  # 根据HAR，对于特定等级访问，这个是false
                    "post_metadata": {"image_order": [media_id]},  # 重要：图片顺序
                    "teaser_text": POST_CONTENT_HTML.split("</p>")[
                                       0] + "</p>" if "</p>" in POST_CONTENT_HTML else POST_CONTENT_HTML[:140],
                    # 简单的预告文本
                    # 其他HAR中可能存在的属性，如 "new_post_email_type": "preview_only", "is_preview_blurred": True 等
                    "is_monetized": False,  # HAR
                    "new_post_email_type": "preview_only",  # HAR
                    "preview_asset_type": "default",  # HAR
                    "thumbnail_position": None,  # HAR
                    "video_preview_start_ms": None,  # HAR
                    "video_preview_end_ms": None,  # HAR
                    "is_preview_blurred": True,  # HAR
                    "allow_preview_in_rss": True,  # HAR
                },
                "relationships": {
                    "access_rule": {"data": {"type": "access-rule", "id": TARGET_ACCESS_RULE_ID}},
                    "access_rules": {"data": [{"id": TARGET_ACCESS_RULE_ID, "type": "access-rule"}]},
                    "user_defined_tags": {"data": []},  # 如果有标签，在这里添加
                    "collections": {"data": []}  # 如果要添加到合集
                }
            },
            "included": [  # 需要包含 access_rule 定义
                {"type": "access-rule", "id": TARGET_ACCESS_RULE_ID, "attributes": {}}  # attributes为空，因为是引用现有规则
            ],
            "meta": {
                "auto_save": False,  # 发布时通常为false
                "send_notifications": True  # 是否发送通知
            }
        }

        response_data = patreon_api_request(driver, final_publish_url, 'PATCH', publish_payload,
                                            {'Referer': referer_media})
        if 'error' in response_data:
            raise Exception(f"最终发布帖子失败: {response_data['error']}")

        published_post_url = response_data['data']['data']['attributes'].get('patreon_url')
        print(f"   帖子成功发布/更新！URL: {published_post_url}")
        print(f"   Patreon Post URL: https://www.patreon.com{response_data['data']['data']['attributes'].get('url')}")


    except Exception as e:
        print(f"发生错误: {e}")
        if post_id:
            print(f"帖子处理中出错，Post ID: {post_id}")
        if media_id:
            print(f"媒体处理中出错，Media ID: {media_id}")
    finally:
        if driver:
            driver.quit()
        print("脚本执行完毕。")


if __name__ == "__main__":
    if not os.path.exists(IMAGE_PATH):
        print(f"错误: 图片文件未找到 '{IMAGE_PATH}'")
    elif CSRF_TOKEN == "YOUR_CSRF_SIGNATURE_HERE" or RAW_COOKIE_STRING.startswith(
            "patreon_locale_code=en-US; YOUR_OTHER_COOKIES_HERE"):
        print("错误: 请在脚本中配置 CSRF_TOKEN 和 RAW_COOKIE_STRING")
    elif TARGET_ACCESS_RULE_ID == "YOUR_TARGET_ACCESS_RULE_ID":
        print("错误: 请在脚本中配置 TARGET_ACCESS_RULE_ID")
    else:
        main()
