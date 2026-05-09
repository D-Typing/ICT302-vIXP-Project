from django.core.management.base import BaseCommand
from django.utils import timezone
from pages.models import ParticipantRegistration, BGPSessionStatus
from pages.frr_connector import (
    get_bgp_summary_ipv4,
    get_bgp_summary_ipv6,
    get_advertised_routes,
)


class Command(BaseCommand):
    help = 'Sync BGP session data from FRRouting into Django database'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.HTTP_INFO('\n[FRR Sync] Starting...'))

        ipv4_data = get_bgp_summary_ipv4()
        ipv6_data = get_bgp_summary_ipv6()

        if ipv4_data:
            peers = ipv4_data.get('ipv4Unicast', {}).get('peers', {})
            self.stdout.write(f"  Found {len(peers)} IPv4 peers")
            self.sync_peers(peers, family='ipv4')
        else:
            self.stdout.write(self.style.WARNING('  Could not fetch IPv4 BGP data'))

        if ipv6_data:
            peers = ipv6_data.get('ipv6Unicast', {}).get('peers', {})
            self.stdout.write(f"  Found {len(peers)} IPv6 peers")
            self.sync_peers(peers, family='ipv6')
        else:
            self.stdout.write(self.style.WARNING('  Could not fetch IPv6 BGP data'))

        self.stdout.write(self.style.SUCCESS('[FRR Sync] Done.\n'))

    def sync_peers(self, peers, family):
        for peer_ip, peer_data in peers.items():
            asn = peer_data.get('remoteAs')
            raw_state = peer_data.get('state', 'Idle')
            prefixes_received = peer_data.get('prefixReceivedCount', 0)
            uptime_ms = peer_data.get('peerUptimeMsec', 0)

            # Get advertised prefix count
            prefixes_advertised = 0
            if raw_state == 'Established':
                prefixes_advertised = get_advertised_routes(peer_ip, family)

            # Match to ParticipantRegistration by ASN
            # Only sync approved participants
            try:
                participant = ParticipantRegistration.objects.get(
                    asn=asn,
                    status=ParticipantRegistration.Status.APPROVED
                )
            except ParticipantRegistration.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"    Skipping AS{asn} ({peer_ip}) — not found or not approved"
                    )
                )
                continue

            # Determine route server based on which RS the peer is connected to
            # You may need to adjust this logic based on your FRR setup
            route_server = 'RS1'
            if participant.connect_rs2 and not participant.connect_rs1:
                route_server = 'RS2'

            session, created = BGPSessionStatus.objects.update_or_create(
                participant=participant,
                route_server=route_server,
                family=family,
                defaults={
                    'session_state': raw_state,
                    'prefixes_received': prefixes_received,
                    'prefixes_advertised': prefixes_advertised,
                    'uptime_seconds': uptime_ms // 1000,
                    'last_seen': timezone.now(),
                }
            )

            tag = 'NEW' if created else 'UPD'
            self.stdout.write(
                f"    [{tag}] AS{asn} ({peer_ip}) — {raw_state} | "
                f"Rcvd: {prefixes_received} | Sent: {prefixes_advertised}"
            )