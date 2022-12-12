#!/usr/bin/python
# ================================
# (C)2021-2022 Dmytro Holub
# heap3d@gmail.com
# --------------------------------
# modo python
# EMAG
# place center of items in hierarchy at the center of rotation
import lx
import modo
import modo.constants as c

accepted_types = (c.MESH_TYPE, c.MESHINST_TYPE, c.LOCATOR_TYPE)
processed_items = set()
failed_items = set()

scene = modo.scene.current()


def get_rotation_parent(source):
    if source is None:
        return None
    parent = get_parent(source)
    if parent is None:
        return None
    if rotation_parent_marker in parent.name:
        return parent
    return get_rotation_parent(parent)


def get_parent(source):
    if source is None:
        return None
    return source.parent


def get_working_items_list(source, root):
    if source is None:
        print("source item: None")
        return set()
    # stop at downstream rotation parent
    if rotation_parent_marker in source.name:
        if source != root:
            return set()
    working_list = set()
    # recursive call for all children
    for child in source.children(recursive=False):
        working_list.add(child)
        working_list = working_list.union(
            get_working_items_list(source=child, root=root)
        )
    return working_list


def freeze_child_position(items_to_proceed, source, root):
    if source is None:
        print("freeze_child_position: source is None")
        return
    if items_to_proceed is None:
        print("freeze_child_position: items list is None")
        return
    if len(items_to_proceed) == 0:
        print("freeze_child_position: items list is void")
        return
    # stop at downstream rotation parent
    if rotation_parent_marker in source.name:
        if source != root:
            print("next rotation parent marker reached")
            return
    # freeze position for children meshes
    for child in source.children(recursive=False, itemType=c.MESH_TYPE):
        if child in items_to_proceed:
            child.select(replace=True)
            try:
                lx.eval("!transform.freeze translation")
            except Exception:
                print("Item failed to freeze translation: {}".format(child.name))
                failed_items.add(child)
    # recursive call freeze_child_position() for all children
    for child in source.children(recursive=False):
        if c.item_type(child.type) == c.MESHINST_TYPE:
            if child in items_to_proceed:
                child.select(replace=True)
                lx.eval("transform.reset translation")
        if child in items_to_proceed:
            processed_items.add(child)
        freeze_child_position(
            items_to_proceed=items_to_proceed, source=child, root=root
        )


def fix_meshref(items_list):
    if items_list is None or len(items_list) == 0:
        return list()
    meshref_list = list()
    for input_item in items_list:
        if ":" in input_item.id:
            if c.item_type(input_item.type) == c.MESH_TYPE:
                meshref_list.append(input_item)
    if len(meshref_list) == 0:
        return items_list
    meshref_copy_dict = dict()
    ready_item_list = list(items_list)
    processed_instances = set()
    delete_group_list = set()
    # duplicate meshref to make mesh item
    for meshref in meshref_list:
        # create copy of meshref
        meshref_copy = scene.duplicateItem(meshref, instance=False)
        meshref_copy.name = (
            meshref.name[: meshref.name.rfind(" (")]
            + " - "
            + meshref.id[: meshref.id.rfind(":")]
            + "_copy"
        )
        # replace meshref by mesh copy
        replace_mesh(meshref, meshref_copy)
        if meshref in ready_item_list:
            ready_item_list.remove(meshref)
        ready_item_list.append(meshref_copy)
        # map meshref to meshref copy (meshref dict)
        meshref_copy_dict[meshref] = meshref_copy

    # deal with meshref instances
    instance_list = list()
    for input_item in items_list:
        if c.item_type(input_item.type) == c.MESHINST_TYPE:
            if input_item in processed_instances:
                continue
            instance_source = get_instance_source(input_item)
            if ":" in instance_source.id:
                instance_source.select(replace=True)
                lx.eval("select.itemInstances")
                selected_instances = scene.selectedByType(c.MESHINST_TYPE)
                instance_list.extend(selected_instances)
                processed_instances = processed_instances.union(instance_list)

    # get source of instance of meshref
    instance_set = set(instance_list)
    for meshref_instance in instance_set:
        source = get_instance_source(meshref_instance)
        # if meshref hasn't a copy then create a copy (use meshref dict), create instance of meshref copy
        if source in meshref_copy_dict:
            meshref_copy = meshref_copy_dict[source]
        else:
            meshref_copy = scene.duplicateItem(source)
        meshref_copy_instance = scene.duplicateItem(meshref_copy, instance=True)
        # replace all meshref instances with instance of meshref copy
        replace_mesh(meshref_instance, meshref_copy_instance)
        if meshref_instance in ready_item_list:
            ready_item_list.remove(meshref_instance)
        ready_item_list.append(meshref_copy_instance)

    delete_group_list = delete_group_list.union(meshref_list)
    delete_group_list = delete_group_list.union(processed_instances)

    # create group DeleteToRender and turn eye off
    ref_group = get_group(ref_group_name)
    # add meshref to meshref_group
    scene.deselect()
    lx.eval("select.drop item")
    lx.eval('select.subItem "{}" set'.format(ref_group.id))
    # turn off visibility
    lx.eval("item.state vis off group")
    for input_item in delete_group_list:
        if (
            c.item_type(input_item.type) == c.MESH_TYPE
            or c.item_type(input_item.type) == c.MESHINST_TYPE
        ):
            lx.eval('select.subItem "{}" add'.format(input_item.id))
    # add all selected meshrefs to meshref_group
    lx.eval("group.edit add item")
    return ready_item_list


def replace_mesh(mesh_old, mesh_new):
    # hierarchy
    for child in mesh_old.children():
        child.setParent(mesh_new)
    parent = mesh_old.parent
    mesh_new.setParent(parent)
    # transforms
    mesh_old.select(replace=True)
    mesh_new.select()
    lx.eval("item.match item pos")
    lx.eval("item.match item rot")
    lx.eval("item.match item scl")


def get_instance_list_from_instance(instance_mesh):
    if instance_mesh is None:
        return list()
    # get source of instance then get all instance from source
    source_mesh = get_instance_source(instance_mesh)
    return get_instance_list_from_source(source_mesh)


def get_instance_source(instance):
    if instance is None:
        return None
    if c.item_type(instance.type) == c.MESH_TYPE:
        return instance
    try:
        instance.select(replace=True)
        lx.eval("select.itemSourceSelected")
    except Exception:
        return instance
    source = scene.selected[0]
    if c.item_type(source.type) == c.MESHINST_TYPE:
        get_instance_source(source)
    return source


def get_instance_list_from_source(source_mesh):
    if source_mesh is None:
        return list()
    source_mesh.select(replace=True)
    try:
        lx.eval("select.itemInstances")
    except Exception:
        # return void list if no instances
        return list()
    recursive_instance_list = list()
    instance_list = scene.selectedByType(c.MESHINST_TYPE)
    for meshinst in instance_list:
        # accumulate list of instances for all meshinst items
        recursive_instance_list = (
            recursive_instance_list + get_instance_list_from_source(meshinst)
        )
    return instance_list + recursive_instance_list


def get_group(name):
    try:
        failed_grp = scene.item(name)
    except LookupError:
        failed_grp = scene.addGroup(name)
    return failed_grp


print()
print("Start...")
# ---------- ----------

rotation_parent_marker = lx.eval("user.value h3d_rcr_rotation_marker ?")
ref_group_name = lx.eval("user.value h3d_rcr_meshref_grp_name ?")
failed_group_name = lx.eval("user.value h3d_rcr_failed_grp_name ?")

for rotation_parent in scene.items(
    itype=c.LOCATOR_TYPE, name="*{}*".format(rotation_parent_marker)
):
    # get list of working items
    working_items_list = get_working_items_list(
        source=rotation_parent, root=rotation_parent
    )

    # replace reference item by copy, manage reference instances
    prepared_items = fix_meshref(working_items_list)

    # iterate (recursive) downstream and freeze mesh position for children
    freeze_child_position(
        items_to_proceed=prepared_items, source=rotation_parent, root=rotation_parent
    )
    for item in processed_items:
        if c.item_type(item.type) == c.MESHINST_TYPE:
            item.select(replace=True)
            lx.eval("transform.reset translation")

failed_items_group = get_group(failed_group_name)
scene.deselect()
lx.eval("select.drop item")
print("failed items: {}".format(failed_items))
for item in failed_items:
    lx.eval('select.subItem "{}" add'.format(item.id))
lx.eval('select.subItem "{}" add'.format(failed_items_group.id))
lx.eval("group.edit add item")

scene.deselect()
for item in processed_items:
    item.select()

# ---------- ----------
print("Done.")
