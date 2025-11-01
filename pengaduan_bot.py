def get_user_contact_info(user):
    """Dapatkan informasi kontak user dengan handle username yang tidak ada"""
    user_id = user.id
    username = user.username
    first_name = escape_html(user.first_name or "")
    last_name = escape_html(user.last_name or "")
    
    # Format nama lengkap
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        full_name = "Tidak ada nama"
    
    # Format info kontak
    if username:
        contact_info = f"@{username}"
        contact_method = "Username"
    else:
        contact_info = f"ID: {user_id}"
        contact_method = "User ID"
    
    return {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "contact_info": contact_info,
        "contact_method": contact_method
    }
