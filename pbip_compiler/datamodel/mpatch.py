from    pbix_mcp.formats.datamodel_roundtrip    import compress_datamodel, decompress_datamodel
from    pbix_mcp.formats                        import abf_rebuild
from    zipfile                                 import ZipFile, ZipInfo, ZIP_STORED, ZIP_DEFLATED
from    io                                      import BytesIO
from    sqlite3                                 import Connection

def patch_partition_m(pbix_bytes: bytes, m_by_table: dict[str, str]) -> bytes:

    if not m_by_table:
        return pbix_bytes

    with ZipFile(BytesIO(pbix_bytes)) as zf:
        datamodel : bytes= zf.read("DataModel")

    abf : bytes = decompress_datamodel(datamodel)

    def modifier(conn: Connection) -> None:
        for table_name, m_expr in m_by_table.items():
            conn.execute(
                "UPDATE [Partition] SET QueryDefinition = ? "
                "WHERE Name = ? AND QueryDefinition IS NOT NULL",
                (m_expr, table_name),
            )

    new_abf         : bytes = abf_rebuild.rebuild_abf_with_modified_sqlite(abf, modifier)
    new_datamodel   : bytes = compress_datamodel(new_abf)

    buf : BytesIO = BytesIO()
    with ZipFile(BytesIO(pbix_bytes)) as zf_in:
        with ZipFile(buf, "w", ZIP_DEFLATED) as zf_out:
            for name in zf_in.namelist():
                info : ZipInfo = ZipInfo(filename=name)
                if name == "DataModel":
                    info.compress_type = ZIP_STORED
                    zf_out.writestr(info, new_datamodel)
                else:
                    info.compress_type = ZIP_DEFLATED
                    zf_out.writestr(info, zf_in.read(name))
    return buf.getvalue()
