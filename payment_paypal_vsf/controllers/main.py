# -*- coding: utf-8 -*-
# Copyright 2023 ERPGAP/PROMPTEQUATION LDA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
import pprint
import werkzeug

from werkzeug.exceptions import Forbidden

from odoo import http, _
from odoo.http import request
from odoo.addons.payment_paypal.const import PAYMENT_STATUS_MAPPING
from odoo.addons.payment_paypal.controllers.main import PaypalController
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

_logger = logging.getLogger(__name__)


class PaypalControllerInherit(PaypalController):
    _return_url = '/payment/paypal/return/'
    _webhook_url = '/payment/paypal/webhook/'
    _return_with_reference_url = '/payment/paypal/return/<string:reference>/'

    @http.route(
        [_return_url, _return_with_reference_url], type='http', auth='public', methods=['GET', 'POST'], csrf=False,
        save_session=False
    )
    def paypal_return_from_checkout(self, reference, **pdt_data):
        """ Process the PDT notification sent by PayPal after redirection from checkout.

        The PDT (Payment Data Transfer) notification contains the parameters necessary to verify the
        origin of the notification and retrieve the actual notification data, if PDT is enabled on
        the account. See https://developer.paypal.com/api/nvp-soap/payment-data-transfer/.

        The route accepts both GET and POST requests because PayPal seems to switch between the two
        depending on whether PDT is enabled, whether the customer pays anonymously (without logging
        in on PayPal), whether the customer cancels the payment, whether they click on "Return to
        Merchant" after paying, etc.

        The route is flagged with `save_session=False` to prevent Odoo from assigning a new session
        to the user if they are redirected to this route with a POST request. Indeed, as the session
        cookie is created without a `SameSite` attribute, some browsers that don't implement the
        recommended default `SameSite=Lax` behavior will not include the cookie in the redirection
        request from the payment provider to Odoo. As the redirection to the '/payment/status' page
        will satisfy any specification of the `SameSite` attribute, the session of the user will be
        retrieved and with it the transaction which will be immediately post-processed.
        """
        _logger.info("handling redirection from PayPal with data:\n%s", pprint.pformat(pdt_data))
        if not pdt_data:  # The customer has canceled or paid then clicked on "Return to Merchant"
            pass  # Redirect them to the status page to browse the (currently) draft transaction
        else:
            # Check the origin of the notification
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                'paypal', pdt_data
            )

            # Check the Order and respective website related with the transaction
            # Check the payment_return url for the success and error pages
            # Pass the transaction_id on the session
            sale_order_ids = tx_sudo.sale_order_ids.ids
            sale_order = request.env['sale.order'].sudo().search([
                ('id', 'in', sale_order_ids), ('website_id', '!=', False)
            ], limit=1)

            # Get Website
            website = sale_order.website_id
            # Redirect to VSF
            vsf_payment_success_return_url = website.vsf_payment_success_return_url
            vsf_payment_error_return_url = website.vsf_payment_error_return_url

            request.session["__payment_monitored_tx_ids__"] = [tx_sudo.id]

            try:
                notification_data = self._verify_pdt_notification_origin(pdt_data, tx_sudo)
            except Forbidden:
                _logger.exception("could not verify the origin of the PDT; discarding it")
            else:
                # Handle the notification data
                tx_sudo._handle_notification_data('paypal', notification_data)

            # Transaction created on VSF
            if tx_sudo and tx_sudo.created_on_vsf:
                payment_status = notification_data.get('payment_status')
                if payment_status in PAYMENT_STATUS_MAPPING['done']:
                    # Confirm sale order
                    PaymentPostProcessing().poll_status()
                    # Redirect to Success Page
                    return werkzeug.utils.redirect(vsf_payment_success_return_url)

                # Redirect to Error Page
                return werkzeug.utils.redirect(vsf_payment_error_return_url)

        # Used to cancel one payment, using the button "Cancel and return"
        if reference:
            tx_sudo = request.env['payment.transaction'].sudo().search([('reference', '=', reference)], limit=1)
            if tx_sudo and tx_sudo.id and tx_sudo.created_on_vsf:
                # Check the Order and respective website related with the transaction
                # Check the payment_return url for the Error Page
                sale_order_ids = tx_sudo.sale_order_ids.ids
                sale_order = request.env['sale.order'].sudo().search([
                    ('id', 'in', sale_order_ids), ('website_id', '!=', False)
                ], limit=1)
                # Get Website
                website = sale_order.website_id
                # Redirect to VSF
                vsf_payment_error_return_url = website.vsf_payment_error_return_url
                # Redirect to Error Page
                return werkzeug.utils.redirect(vsf_payment_error_return_url)

        return request.redirect('/payment/status')
