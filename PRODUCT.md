# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- **Store supervisor** (primary): a manager or floor supervisor in the back office of a supermarket. They glance at the CCTV dashboard between other tasks to decide when to open or close checkouts and where to send cashiers. They are not a security professional and don't watch the feeds continuously.
- **Admin** (same person or the installer): sets things up once and maintains them. Adds cameras (IP, RTSP URL, password) and maps hallways, checkouts and cashier zones on a camera snapshot.
- **Shoppers**: read the public LCD screens from 2–8 m away for a second or two, to pick a checkout.

## Product Purpose
Computer vision watches the hallways that lead to the checkouts. It counts the people waiting, says which checkouts are free, busy or closed (staffed or not), and shows this live on LCD screens and on an admin CCTV dashboard. Success: shorter, better-balanced queues, and supervisors who open a checkout *before* the queue gets long.

## Positioning
Checkout state comes from the camera feeds the store already has, using zones an admin draws on a snapshot. There's no hardware per checkout and no POS integration. Faces are always blurred: privacy is part of the product, not an option.

## Operating context
- **Deployment:** a single-store pilot first (one supermarket, local network, Docker on one GPU machine). Multi-store comes later.
- **UI language:** French.
- **LCD screens:** kiosk browsers on the store network, possibly without internet access, so no external CDN dependencies.

## Brand
"Smart Surveillance" is a working name. There's no logo, palette or brand commitment yet, so the identity is open.

## Accessibility
WCAG AA contrast. State is never shown by color alone, partly because of red–green color blindness among supervisors and shoppers. The LCD must be legible from a distance.

## Terminology
Couloir (hallway / queue zone), Caisse (checkout), Zone caissier (cashier zone), libre / occupée / fermée, en attente (waiting), en direct / hors ligne (live / offline).
