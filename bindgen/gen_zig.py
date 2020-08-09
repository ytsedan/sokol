#-------------------------------------------------------------------------------
#   Read output of gen_json.py and generate Zig language bindings.
#
#   Zig coding style:
#   - types are PascalCase
#   - functions are camelCase
#   - otherwise snake_case
#-------------------------------------------------------------------------------
import json
import re

struct_types = []
c_struct_types = []     # structs that have a C compatible memory layout
enum_types = []
enum_items = {}

re_1d_array = re.compile("^\w*\s\[\d*\]$")
re_2d_array = re.compile("^\w*\s\[\d*\]\[\d*\]$")

prim_types = {
    'int':      'i32',
    'bool':     'bool',
    'int8_t':   'i8',
    'uint8_t':  'u8',
    'int16_t':  'i16',
    'uint16_t': 'u16',
    'int32_t':  'i32',
    'uint32_t': 'u32',
    'int64_t':  'i64',
    'uint64_t': 'u64',
    'float':    'f32',
    'double':   'f64'
}

prim_defaults = {
    'int':      '0',
    'bool':     'false',
    'int8_t':   '0',
    'uint8_t':  '0',
    'int16_t':  '0',
    'uint16_t': '0',
    'int32_t':  '0',
    'uint32_t': '0',
    'int64_t':  '0',
    'uint64_t': '0',
    'float':    '0.0',
    'double':   '0.0'
}

out_lines = ''
def l(s):
    global out_lines
    out_lines += s + '\n'

# PREFIX_BLA_BLUB to bla_blub
def as_const_name(s, prefix):
    outp = s.lower()
    if outp.startswith(prefix):
        outp = outp[len(prefix):]
    return outp

def as_zig_prim_type(s):
    return prim_types[s]

# prefix_bla_blub => BlaBlub
def as_zig_type(s):
    parts = s.lower().split('_')[1:]
    outp = ''
    for part in parts:
        outp += part.capitalize()
    return outp

# PREFIX_ENUM_BLA => Bla, _PREFIX_ENUM_BLA => Bla
def as_enum_item_name(s):
    outp = s
    if outp.startswith('_'):
        outp = outp[1:]
    parts = outp.split('_')[2:]
    outp = '_'.join(parts)
    if outp[0].isdigit():
        outp = '_' + outp
    return outp

def enum_default_item(enum_name):
    return enum_items[enum_name][0]

def is_prim_type(s):
    return s in prim_types

def is_struct_type(s):
    return s in struct_types

def is_enum_type(s):
    return s in enum_types

def is_string_ptr(s):
    return s == "const char *"

def is_1d_array_type(s):
    return re_1d_array.match(s)

def is_2d_array_type(s):
    return re_2d_array.match(s)

def type_default_value(s):
    return prim_defaults[s]

def extract_array_type(s):
    return s[:s.index('[')].strip()

def extract_1d_array_num(s):
    return s[s.index('['):].strip('[]').strip()

# test if a struct has a C compatible memory layout
def struct_is_c_compatible(decl):
    c_comp = True;
    for field in decl['fields']:
        field_type = field['type']
        if is_struct_type(field_type):
            if field_type not in c_struct_types:
                c_comp = False
        # FIXME
    print(f"{decl['name']} C compatible: {c_comp}")
    return c_comp

def gen_struct(decl, prefix):
    zig_type = as_zig_type(decl['name'])
    if decl['name'] in c_struct_types:
        l(f"pub const {zig_type} = extern struct {{")
    else:
        l(f"pub const {zig_type} = struct {{")
    l(f"    pub fn init(options: anytype) {zig_type} {{ var item: {zig_type} = .{{ }}; init_with(&item, options); return item; }}")
    for field in decl['fields']:
        field_name = field['name']
        field_type = field['type']
        if is_prim_type(field_type):
            l(f"    {field_name}: {as_zig_prim_type(field_type)} = {type_default_value(field_type)},")
        elif is_struct_type(field_type):
            l(f"    {field_name}: {as_zig_type(field_type)} = .{{ }},")
        elif is_enum_type(field_type):
            l(f"    {field_name}: {as_zig_type(field_type)} = .{enum_default_item(field_type)},")
        elif is_string_ptr(field_type):
            l(f"    {field_name}: ?[*:0]const u8 = null,")
        elif is_1d_array_type(field_type):
            array_type = extract_array_type(field_type)
            array_num  = extract_1d_array_num(field_type)
            if is_prim_type(array_type):
                zig_type = as_zig_prim_type(array_type)
                t0 = f"[{array_num}]{zig_type}"
                t1 = f"[_]{zig_type}"
                def_val = type_default_value(array_type)
                l(f"    {field_name}: {t0} = {t1}{{{def_val}}} ** {array_num},")
            elif is_struct_type(array_type):
                zig_type = as_zig_type(array_type)
                t0 = f"[{array_num}]{zig_type}"
                t1 = f"[_]{zig_type}"
                l(f"    {field_name}: {t0} = {t1}{{ .{{ }} }} ** {array_num},")
            else:
                l(f"//    FIXME: ??? array {field_name}: {field_type} => {array_type} [{array_num}]")
        else:
            l(f"//  {field_name}: {field_type};")
    l("};")

def gen_consts(decl, prefix):
    for item in decl['items']:
        l(f"pub const {as_const_name(item['name'], prefix)} = {item['value']};")

def gen_enum(decl, prefix):
    l(f"pub const {as_zig_type(decl['name'])} = extern enum(i32) {{")
    for item in decl['items']:
        item_name = as_enum_item_name(item['name'])
        if item_name != "FORCE_U32":
            if 'value' in item:
                l(f"    {item_name} = {item['value']},")
            else:
                l(f"    {item_name},")
    l("};")

def gen_func(decl, prefix):
    pass

def gen_helper_funcs(inp):
    if inp['module'] == 'sokol_gfx':
        l('fn init_with(target_ptr: anytype, opts: anytype) void {')
        l('    switch (@typeInfo(@TypeOf(target_ptr.*))) {')
        l('        .Array => {')
        l('            inline for (opts) |item, i| {')
        l('                init_with(&target_ptr.*[i], opts[i]);')
        l('            }')
        l('        },')
        l('        .Struct => {')
        l('            inline for (@typeInfo(@TypeOf(opts)).Struct.fields) |field| {')
        l('                init_with(&@field(target_ptr.*, field.name), @field(opts, field.name));')
        l('            }')
        l('        },')
        l('        else => {')
        l('            target_ptr.* = opts;')
        l('        }')
        l('    }')
        l('}')

def pre_parse(inp):
    global struct_types
    global enum_types
    for decl in inp['decls']:
        kind = decl['kind']
        if kind == 'struct':
            struct_types.append(decl['name'])
            if struct_is_c_compatible(decl):
                c_struct_types.append(decl['name'])
        elif kind == 'enum':
            enum_name = decl['name']
            enum_types.append(enum_name)
            enum_items[enum_name] = []
            for item in decl['items']:
                enum_items[enum_name].append(as_enum_item_name(item['name']))

def gen_module(inp):
    l('// machine generated, do not edit')
    l('')
    l('//--- helper functions ---')
    gen_helper_funcs(inp)
    pre_parse(inp)
    l('//--- API declarations ---')
    prefix = inp['prefix']
    for decl in inp['decls']:
        kind = decl['kind']
        if kind == 'struct':
            gen_struct(decl, prefix)
        elif kind == 'consts':
            gen_consts(decl, prefix)
        elif kind == 'enum':
            gen_enum(decl, prefix)
        elif kind == 'func':
            gen_func(decl, prefix)

def gen_zig(input_path, output_path):
    try:
        print(f">>> {input_path} => {output_path}")
        with open(input_path, 'r') as f_inp:
            inp = json.load(f_inp)
            gen_module(inp)
            with open(output_path, 'w') as f_outp:
                f_outp.write(out_lines)
    except EnvironmentError as err:
        print(f"{err}")

def main():
    gen_zig('sokol_gfx.json', 'sokol_gfx.zig')

if __name__ == '__main__':
    main()
