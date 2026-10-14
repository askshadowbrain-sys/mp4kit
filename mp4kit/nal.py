"""H.264 elementary stream. Episode 2: length labels in mdat. Episode 3: NAL header, types, bit reader.
Episode 4: SPS, PPS, picture size, slice headers."""


def iter_length_prefixed(data, start, end, length_size=4):
    """Yield (offset of the length field, NAL bytes) for each unit in data[start:end]."""
    at = start
    while at < end:
        length_field = data[at:at + length_size]
        size = int.from_bytes(length_field, "big")
        first = at + length_size
        nal_bytes = bytes(data[first:first + size])
        yield at, nal_bytes
        at = first + size


NAL_TYPES = {1: "non-IDR slice", 5: "IDR slice", 6: "SEI", 7: "SPS", 8: "PPS", 9: "AUD"}


def nal_header(first_byte):
    """Split a NAL's first byte into (forbidden_zero_bit, nal_ref_idc, nal_unit_type)."""
    forbidden_zero_bit = first_byte >> 7
    nal_ref_idc = (first_byte >> 5) & 3
    nal_unit_type = first_byte & 31
    return forbidden_zero_bit, nal_ref_idc, nal_unit_type


class BitReader:
    """Reads a byte string one bit at a time, most significant bit first."""

    def __init__(self, data):
        self.data = bytes(data)
        self.pos = 0

    def u(self, n):
        """Read n bits as an unsigned number."""
        value = 0
        for _ in range(n):
            byte = self.data[self.pos >> 3]
            bit = (byte >> (7 - (self.pos & 7))) & 1
            value = (value << 1) | bit
            self.pos += 1
        return value

    def ue(self):
        """Read an unsigned Exp-Golomb number."""
        zeros = 0
        while self.u(1) == 0:
            zeros += 1
        return (1 << zeros) - 1 + self.u(zeros)

    def se(self):
        """Read a signed Exp-Golomb number."""
        k = self.ue()
        if k & 1:
            return (k + 1) // 2
        return -(k // 2)


HIGH_PROFILES = (100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135)


def _sps_chroma(r, s):
    """Read the High-profile fields of an SPS: chroma format and bit depths."""
    s["chroma_format_idc"], s["bit_depth_luma"], s["bit_depth_chroma"] = 1, 8, 8
    s["separate_colour_plane"] = False
    if s["profile_idc"] not in HIGH_PROFILES:
        return
    s["chroma_format_idc"] = r.ue()
    if s["chroma_format_idc"] == 3:
        s["separate_colour_plane"] = r.u(1) == 1
    s["bit_depth_luma"] = r.ue() + 8
    s["bit_depth_chroma"] = r.ue() + 8
    r.u(1)  # qpprime_y_zero_transform_bypass_flag
    if r.u(1) == 1:  # seq_scaling_matrix_present_flag
        raise ValueError("scaling lists not taught")


def _sps_poc(r, s):
    """Read the picture order count fields of an SPS."""
    s["pic_order_cnt_type"] = r.ue()
    if s["pic_order_cnt_type"] == 0:
        s["log2_max_poc_lsb"] = r.ue() + 4
    elif s["pic_order_cnt_type"] == 1:
        r.u(1)  # delta_pic_order_always_zero_flag
        r.se()  # offset_for_non_ref_pic
        r.se()  # offset_for_top_to_bottom_field
        cycle_length = r.ue()
        for _ in range(cycle_length):
            r.se()  # offset_for_ref_frame[i]


def _sps_frame(r, s):
    """Read the frame/field flags and the cropping window of an SPS."""
    s["frame_mbs_only"] = r.u(1)
    if s["frame_mbs_only"] == 0:
        r.u(1)  # mb_adaptive_frame_field_flag
    r.u(1)  # direct_8x8_inference_flag
    s["crop"] = (0, 0, 0, 0)
    if r.u(1) == 1:  # frame_cropping_flag
        left, right, top, bottom = r.ue(), r.ue(), r.ue(), r.ue()
        s["crop"] = (left, right, top, bottom)


def parse_sps(nal):
    """Read an SPS NAL (H.264 7.3.2.1.1) up to its cropping window."""
    r = BitReader(nal[1:])
    s = {"profile_idc": r.u(8), "constraint_flags": r.u(8), "level_idc": r.u(8)}
    s["sps_id"] = r.ue()
    _sps_chroma(r, s)
    s["log2_max_frame_num"] = r.ue() + 4
    _sps_poc(r, s)
    s["max_num_ref_frames"] = r.ue()
    r.u(1)  # gaps_in_frame_num_value_allowed_flag
    s["width_mbs"] = r.ue() + 1
    s["height_map_units"] = r.ue() + 1
    _sps_frame(r, s)
    return s


def picture_size(sps):
    """The picture's (width, height) in pixels: macroblocks times 16, minus the cropping."""
    if sps["chroma_format_idc"] != 1:
        raise ValueError("only 4:2:0 taught here")
    left, right, top, bottom = sps["crop"]
    width = sps["width_mbs"] * 16 - 2 * (left + right)
    frame_height = (2 - sps["frame_mbs_only"]) * sps["height_map_units"] * 16
    crop_unit_y = 2 * (2 - sps["frame_mbs_only"])
    height = frame_height - crop_unit_y * (top + bottom)
    return width, height


def parse_pps(nal):
    """Read the first three fields of a PPS NAL (H.264 7.3.2.2)."""
    r = BitReader(nal[1:])
    pps_id = r.ue()
    sps_id = r.ue()
    entropy_coding_mode_flag = r.u(1)
    return {"pps_id": pps_id, "sps_id": sps_id, "entropy_coding_mode_flag": entropy_coding_mode_flag}


def read_slice_header(nal, sps, pps):
    """Read the start of a slice header (H.264 7.3.3), up to idr_pic_id."""
    if sps["frame_mbs_only"] == 0:
        raise ValueError("field coding not taught")
    if sps["separate_colour_plane"]:
        raise ValueError("separate colour planes not taught")
    nal_unit_type = nal_header(nal[0])[2]
    r = BitReader(nal[1:])
    h = {"first_mb": r.ue(), "slice_type": r.ue(), "pps_id": r.ue()}
    h["frame_num"] = r.u(sps["log2_max_frame_num"])
    if nal_unit_type == 5:
        h["idr_pic_id"] = r.ue()
    return h


def _read_param_sets(data, at, count):
    """Read `count` parameter sets, each a 2-byte length then the NAL; return (list, next offset)."""
    found = []
    for _ in range(count):
        length = int.from_bytes(data[at:at + 2], "big")
        found.append(bytes(data[at + 2:at + 2 + length]))
        at += 2 + length
    return found, at


def _avcc_params_stopgap(data):
    """Find the first SPS and PPS by searching for b"avcC" (a stopgap: ep13 reads avcC properly)."""
    found_at = data.find(b"avcC")
    if found_at < 0:
        raise ValueError("no avcC in this file")
    at = found_at + 4 + 5  # skip the type, then version, profile, compatibility, level, lengthSize
    sps_count = data[at] & 31
    sps_list, at = _read_param_sets(data, at + 1, sps_count)
    pps_count = data[at]
    pps_list, at = _read_param_sets(data, at + 1, pps_count)
    return sps_list[0], pps_list[0]
