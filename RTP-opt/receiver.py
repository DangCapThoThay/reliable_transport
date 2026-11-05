import argparse
import socket
import sys

from utils import PacketHeader, compute_checksum


def make_ack(seq_num):
    ack_hdr = PacketHeader(type=3, seq_num=seq_num, length=0, checksum=0)
    ack_hdr.checksum = compute_checksum(ack_hdr)
    return bytes(ack_hdr)


def receiver(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))

    expected_seq = 1
    received_buffer = {}
    connected = False
    end_seq = None

    while True:
        pkt, address = s.recvfrom(2048)

        if len(pkt) < 16:
            continue

        pkt_header = PacketHeader(pkt[:16])
        msg = pkt[16 : 16 + pkt_header.length]

        if len(msg) != pkt_header.length:
            continue
        pkt_checksum = pkt_header.checksum
        pkt_header.checksum = 0
        computed_checksum = compute_checksum(pkt_header / msg)
        if pkt_checksum != computed_checksum:
            continue

        if pkt_header.type == 0:
            connected = True
            expected_seq = 1
            end_seq = None
            received_buffer.clear()
            s.sendto(make_ack(1), address)

        elif pkt_header.type == 2:
            if not connected:
                continue

            seq_num = pkt_header.seq_num

            if seq_num >= expected_seq + window_size:
                continue

            if seq_num >= expected_seq:
                received_buffer[seq_num] = msg
                while expected_seq in received_buffer:
                    sys.stdout.buffer.write(received_buffer.pop(expected_seq))
                    expected_seq += 1
                sys.stdout.flush()

            s.sendto(make_ack(seq_num), address)

            if end_seq is not None and expected_seq == end_seq:
                for _ in range(5):
                    s.sendto(make_ack(end_seq), address)
                sys.stdout.flush()
                break

        elif pkt_header.type == 1:
            if connected:
                end_seq = pkt_header.seq_num
                s.sendto(make_ack(end_seq), address)
                if expected_seq == end_seq:
                    for _ in range(5):
                        s.sendto(make_ack(end_seq), address)
                    sys.stdout.flush()
                    break

    s.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "receiver_ip", help="The IP address of the host that receiver is running on"
    )
    parser.add_argument(
        "receiver_port", type=int, help="The port number on which receiver is listening"
    )
    parser.add_argument(
        "window_size", type=int, help="Maximum number of outstanding packets"
    )
    args = parser.parse_args()

    receiver(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
