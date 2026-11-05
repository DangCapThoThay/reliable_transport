import argparse
import socket
import sys
import time

from utils import PacketHeader, compute_checksum

TIMEOUT = 0.5
MAX_PAYLOAD = 1472 - 16


def make_packet(pkt_type, seq_num, payload=b""):
    pkt_header = PacketHeader(type=pkt_type, seq_num=seq_num, length=len(payload), checksum=0)
    pkt_header.checksum = compute_checksum(pkt_header / payload)
    return bytes(pkt_header / payload)


def read_ack(raw):
    if len(raw) < 16:
        return None
    pkt_header = PacketHeader(raw[:16])
    msg = raw[16 : 16 + pkt_header.length]
    if len(msg) != pkt_header.length:
        return None
    pkt_checksum = pkt_header.checksum
    pkt_header.checksum = 0
    if pkt_header.type != 3 or pkt_checksum != compute_checksum(pkt_header / msg):
        return None
    return pkt_header.seq_num


def sender(receiver_ip, receiver_port, window_size):
    address = (receiver_ip, receiver_port)
    message = sys.stdin.buffer.read()
    chunks = [message[i : i + MAX_PAYLOAD] for i in range(0, len(message), MAX_PAYLOAD)]
    total = len(chunks)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    s.settimeout(TIMEOUT)
    while True:
        s.sendto(make_packet(0, 0), address)
        try:
            ack = read_ack(s.recvfrom(2048)[0])
        except socket.timeout:
            continue
        if ack == 1:
            break

    base = 1
    next_seq = 1
    acked = set()
    deadline = time.monotonic() + TIMEOUT

    while base <= total:
        while next_seq < base + window_size and next_seq <= total:
            s.sendto(make_packet(2, next_seq, chunks[next_seq - 1]), address)
            next_seq += 1

        remain = deadline - time.monotonic()
        if remain <= 0:
            for seq in range(base, next_seq):
                if seq not in acked:
                    s.sendto(make_packet(2, seq, chunks[seq - 1]), address)
            deadline = time.monotonic() + TIMEOUT
            continue

        s.settimeout(remain)
        try:
            ack = read_ack(s.recvfrom(2048)[0])
        except socket.timeout:
            continue

        if ack is not None and base <= ack < next_seq:
            acked.add(ack)
            old_base = base
            while base in acked:
                acked.remove(base)
                base += 1
            if base > old_base:
                deadline = time.monotonic() + TIMEOUT

    end_seq = total + 1
    s.settimeout(TIMEOUT)
    while True:
        s.sendto(make_packet(1, end_seq), address)
        try:
            ack = read_ack(s.recvfrom(2048)[0])
            if ack is not None and ack >= end_seq:
                break
        except socket.timeout:
            continue

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

    sender(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
