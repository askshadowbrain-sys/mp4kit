"""Test helpers: build small synthetic SPS NALs bit by bit (not part of mp4kit)."""


class BitWriter:
    """Write bits, then bytes. The mirror of nal.BitReader."""

    def __init__(self):
        self.bits = ""

    def u(self, n, value):
        self.bits += format(value, f"0{n}b") if n else ""
        return self

    def ue(self, value):
        code = format(value + 1, "b")
        self.bits += "0" * (len(code) - 1) + code
        return self

    def se(self, value):
        return self.ue(2 * value - 1 if value > 0 else -2 * value)

    def to_bytes(self):
        bits = self.bits + "1"  # rbsp_stop_one_bit
        bits += "0" * (-len(bits) % 8)
        return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))


def baseline_sps(poc_fields, level=30, sps_id=0):
    """A Baseline-profile SPS NAL; poc_fields(w) writes the picture order count part."""
    w = BitWriter().u(8, 66).u(8, 0).u(8, level).ue(sps_id)
    w.ue(0)  # log2_max_frame_num - 4
    poc_fields(w)
    w.ue(1).u(1, 0)  # max_num_ref_frames, gaps flag
    w.ue(39).ue(22)  # 40 x 23 macroblocks
    w.u(1, 1).u(1, 1).u(1, 0)  # frame_mbs_only, direct_8x8, no cropping
    return b"\x67" + w.to_bytes()


def high_sps(chroma_format_idc, scaling_matrix=0, frame_mbs_only=1):
    """A High-profile SPS NAL with the given chroma format."""
    w = BitWriter().u(8, 100).u(8, 0).u(8, 30).ue(0)
    w.ue(chroma_format_idc)
    if chroma_format_idc == 3:
        w.u(1, 1)  # separate_colour_plane_flag
    w.ue(0).ue(0).u(1, 0).u(1, scaling_matrix)
    w.ue(0).ue(2).ue(1).u(1, 0).ue(39).ue(22)
    w.u(1, frame_mbs_only)
    if frame_mbs_only == 0:
        w.u(1, 0)
    w.u(1, 1).u(1, 0)
    return b"\x67" + w.to_bytes()
