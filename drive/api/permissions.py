import frappe
from pypika import Order, Query, Table, Field
from frappe.utils.nestedset import rebuild_tree, get_ancestors_of
from drive.api.files import get_entity
from drive.api.files import get_doc_content
from drive.utils.files import get_user_directory
from drive.utils.user_group import get_entity_shared_with_user_groups


@frappe.whitelist()
def get_shared_with_list(entity_name):
    """
    Return the list of users with whom this file or folder has been shared

    :param entity_name: Document-name of this file or folder
    :raises PermissionError: If the user does not have edit permissions
    :return: List of users, with permissions and last modified datetime
    :rtype: list[frappe._dict]
    """

    if not frappe.has_permission(
        doctype="Drive Entity", doc=entity_name, ptype="write", user=frappe.session.user
    ):
        raise frappe.PermissionError

    entity_owner = frappe.db.get_value("Drive Entity", entity_name, "owner")

    users = frappe.db.get_all(
        "DocShare",
        filters={
            "share_doctype": "Drive Entity",
            "share_name": entity_name,
            "everyone": 0,
            "user": ["not in", [frappe.session.user, entity_owner]],
        },
        order_by="name",
        fields=["user", "read", "write", "share", "everyone", "modified"],
    )

    # Extra read to always have the owner and current user sorted first :c
    # Returns current user even though we currently hide share chaining option

    if entity_owner == frappe.session.user:
        current_user = frappe.db.get_all(
            "DocShare",
            filters={
                "share_doctype": "Drive Entity",
                "share_name": entity_name,
                "everyone": 0,
                "user": frappe.session.user,
            },
            fields=["user", "read", "write", "share", "everyone", "modified"],
        )
        users = current_user + users

    else:
        entity_owner = frappe.db.get_all(
            "DocShare",
            filters={
                "share_doctype": "Drive Entity",
                "share_name": entity_name,
                "everyone": 0,
                "user": ["in", [entity_owner, frappe.session.user]],
            },
            order_by="modified",
            fields=["user", "read", "write", "share", "everyone", "modified"],
        )
        users = entity_owner + users

    for user in users:
        user_info = frappe.db.get_value(
            "User", user.user, ["user_image", "full_name"], as_dict=True
        )
        user.update(user_info)

    return users


@frappe.whitelist()
def get_shared_user_group_list(entity_name):
    user_group_list = get_entity_shared_with_user_groups(entity_name)
    return user_group_list


@frappe.whitelist()
def get_shared_by_me(get_all=False, order_by="modified"):
    """
    Return the list of files and folders shared with the current user

    :param entity_name: Document-name of the folder whose contents are to be listed.
    :raises NotADirectoryError: If this DriveEntity doc is not a folder
    :return: List of DriveEntities with permissions
    :rtype: list[frappe._dict]
    """

    DocShare = frappe.qb.DocType("DocShare")
    DriveEntity = frappe.qb.DocType("Drive Entity")
    DriveFavourite = frappe.qb.DocType("Drive Favourite")
    selectedFields = [
        DriveEntity.name,
        DriveEntity.title,
        DriveEntity.is_group,
        DriveEntity.owner,
        DriveEntity.modified,
        DriveEntity.creation,
        DriveEntity.file_size,
        DriveEntity.mime_type,
        DriveEntity.parent_drive_entity,
        DriveEntity.allow_comments,
        DriveEntity.color,
        DriveEntity.document,
        DriveEntity.allow_download,
        DocShare.read,
        DocShare.write,
        DocShare.everyone,
        DocShare.share,
        DriveFavourite.entity.as_("is_favourite"),
    ]

    query = (
        frappe.qb.from_(DriveEntity)
        .left_join(DocShare)
        .on((DocShare.share_name == DriveEntity.name) & (DriveEntity.owner == frappe.session.user))
        .left_join(DriveFavourite)
        .on(
            (DriveFavourite.entity == DriveEntity.name)
            & (DriveFavourite.user == frappe.session.user)
        )
        .select(*selectedFields)
        .where(
            (DriveEntity.is_active == 1)
            & ((DocShare.user != frappe.session.user) | (DocShare.everyone == 1))
        )
        .groupby(DriveEntity.name)
    )
    if get_all:
        return query.run(as_dict=True)

    result = query.orderby(
        order_by.split()[0],
        order=Order.desc if order_by.endswith("desc") else Order.asc,
    ).run(as_dict=True)
    names = [x.name for x in result]
    # Return highest level entity
    return filter(
        lambda x: x.parent_drive_entity not in names,
        result,
    )


@frappe.whitelist()
def get_shared_with_me(get_all=False, order_by="modified"):
    """
    Return the list of files and folders shared with the current user

    :param entity_name: Document-name of the folder whose contents are to be listed.
    :raises NotADirectoryError: If this DriveEntity doc is not a folder
    :return: List of DriveEntities with permissions
    :rtype: list[frappe._dict]
    """

    DocShare = frappe.qb.DocType("DocShare")
    DriveEntity = frappe.qb.DocType("Drive Entity")
    DriveFavourite = frappe.qb.DocType("Drive Favourite")
    selectedFields = [
        DriveEntity.name,
        DriveEntity.title,
        DriveEntity.is_group,
        DriveEntity.owner,
        DriveEntity.modified,
        DriveEntity.creation,
        DriveEntity.file_size,
        DriveEntity.mime_type,
        DriveEntity.parent_drive_entity,
        DriveEntity.allow_comments,
        DriveEntity.color,
        DriveEntity.document,
        DriveEntity.allow_download,
        DocShare.read,
        DocShare.write,
        DocShare.everyone,
        DocShare.share,
        DriveFavourite.entity.as_("is_favourite"),
    ]

    query = (
        frappe.qb.from_(DriveEntity)
        .inner_join(DocShare)
        .on((DocShare.share_name == DriveEntity.name) & (DocShare.user == frappe.session.user))
        .left_join(DriveFavourite)
        .on(
            (DriveFavourite.entity == DriveEntity.name)
            & (DriveFavourite.user == frappe.session.user)
        )
        .select(*selectedFields)
        .where(DriveEntity.is_active == 1)
    )
    if get_all:
        return query.run(as_dict=True)

    result = query.orderby(
        order_by.split()[0],
        order=Order.desc if order_by.endswith("desc") else Order.asc,
    ).run(as_dict=True)
    names = [x.name for x in result]
    # Return highest level entity
    return filter(
        lambda x: x.parent_drive_entity not in names and x.owner != frappe.session.user,
        result,
    )


@frappe.whitelist()
def get_all_my_entities(fields=None):
    """
    Return file data with permissions

    :return: DriveEntity with permissions
    :rtype: frappe._dict
    """

    fields = fields or [
        "name",
        "title",
        "is_group",
        "owner",
        "modified",
        "file_size",
        "mime_type",
    ]
    my_entities = frappe.db.get_list(
        "Drive Entity",
        filters={
            "is_active": 1,
            "owner": frappe.session.user,
            "name": ["!=", get_user_directory().name],
        },
        fields=fields,
    )

    shared_entities = get_shared_with_me(get_all=True)

    all_entities = shared_entities + my_entities
    return list({x["name"]: x for x in all_entities}.values())


@frappe.whitelist(allow_guest=True)
def get_file_with_permissions(entity_name):
    """
    Return file data with permissions

    :param entity_name: Name of file document.
    :raises IsADirectoryError: If this DriveEntity doc is not a file
    :return: DriveEntity with permissions
    :rtype: frappe._dict
    """

    user_access = get_user_access(entity_name)

    if not user_access:
        frappe.throw(
            "PermissionError: Either this file does not exist, or you don't have access to it",
            frappe.PermissionError,
        )

    fields = [
        "name",
        "title",
        "owner",
        "is_group",
        "is_active",
        "modified",
        "creation",
        "file_size",
        "mime_type",
        "allow_comments",
        "allow_download",
    ]
    entity = get_entity(entity_name, fields)
    entity_ancestors = get_ancestors_of("Drive Entity", entity)
    flag = False
    for z_entity_name in entity_ancestors:
        result = frappe.db.exists("Drive Entity", {"name": z_entity_name, "is_active": 0})
        if result:
            flag = True
            break
    if flag == True:
        frappe.throw("Parent Folder has been deleted")
    if entity.is_group:
        frappe.throw("Specified entity is not a file", IsADirectoryError)
    if not entity.is_active:
        frappe.throw("Specified file has been trashed by the owner")

    return entity | user_access


@frappe.whitelist(allow_guest=True)
def get_doc_with_permissions(entity_name):
    """
    Return file data with permissions

    :param entity_name: Name of file document.
    :raises IsADirectoryError: If this DriveEntity doc is not a file
    :return: DriveEntity with permissions
    :rtype: frappe._dict
    """

    user_access = get_user_access(entity_name)

    if not user_access:
        frappe.throw(
            "PermissionError: Either this file does not exist, or you don't have access to it",
            frappe.PermissionError,
        )
    entity = get_doc_content(entity_name)

    return entity | user_access


@frappe.whitelist()
def get_general_access(entity_name):
    """
    Return the general access permissions for the given entity

    :param entity_name: Document-name of the entity whose permissions are to be fetched
    :return: Dict of general access permissions (read, write)
    :rtype: frappe._dict or None
    """

    return frappe.db.get_value(
        "DocShare",
        {"share_name": entity_name, "everyone": 1},
        ["read", "write"],
        as_dict=1,
    )


@frappe.whitelist()
def get_user_access(entity_name):
    """
    Return the user specific access permissions for an entity if it exists or general access permissions

    :param entity_name: Document-name of the entity whose permissions are to be fetched
    :return: Dict of general access permissions (read, write)
    :rtype: frappe._dict or None
    """

    user_access = frappe.db.get_value(
        "DocShare",
        {"share_name": entity_name, "user": frappe.session.user},
        ["read", "write"],
        as_dict=1,
    )

    if user_access:
        if not frappe.has_permission(
            doctype="Drive Entity",
            doc=entity_name,
            ptype="write",
            user=frappe.session.user,
        ):
            frappe.throw(
                "PermissionError: Either this file does not exist, or you don't have access to it",
                frappe.PermissionError,
            )
        return user_access

    return get_general_access(entity_name)
