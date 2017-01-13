#
# Copyright (c) 2016 Nordic Semiconductor ASA
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#   1. Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
#   2. Redistributions in binary form must reproduce the above copyright notice, this
#   list of conditions and the following disclaimer in the documentation and/or
#   other materials provided with the distribution.
#
#   3. Neither the name of Nordic Semiconductor ASA nor the names of other
#   contributors to this software may be used to endorse or promote products
#   derived from this software without specific prior written permission.
#
#   4. This software must only be used in or with a processor manufactured by Nordic
#   Semiconductor ASA, or in or with a processor manufactured by a third party that
#   is used in combination with a processor manufactured by Nordic Semiconductor.
#
#   5. Any software provided in binary or object form under this license must not be
#   reverse engineered, decompiled, modified and/or disassembled.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import multiprocessing
import threading
import logging
import inspect
import traceback
from pc_ble_driver_py.ble_driver import *
from pc_ble_driver_py.observers import *

logging.basicConfig()
log = logging.getLogger(__name__)   

class _Command(object):
    def __init__(self, cmd, *args, **kwargs):
        self.cmd = cmd
        self.args = args
        self.kwargs = kwargs

class _Event(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs
        
class _CommandAck(object):
    def __init__(self, exception=None, result=None):
        self.exception = exception
        self.result = result

class _SerBLEGapAddr(object):
    def __init__(self, ble_gap_addr):
        assert isinstance(ble_gap_addr, BLEGapAddr)
        self.addr_type = ble_gap_addr.addr_type.value
        self.addr = ble_gap_addr.addr

    def deserialize(self):
        return BLEGapAddr(BLEGapAddr.Types(self.addr_type), self.addr)

class _SerBLEAdvData(object):
    def __init__(self, ble_advdata):
        assert isinstance(ble_advdata, BLEAdvData)
        self.records = {k.value: v for k, v in ble_advdata.records.items()}
            
    def deserialize(self):
        return BLEAdvData(**{BLEAdvData.Types(k).name: v for k, v in self.records.items()})
            
class _ObserverMulti(object):
    def __init__(self, event_q):
        self.event_q = event_q
    def on_gap_evt_connected(self, ble_driver, conn_handle, peer_addr, role, conn_params):
        self.event_q.put(_Event('on_gap_evt_connected', 
                                conn_handle=conn_handle, 
                                peer_addr=_SerBLEGapAddr(peer_addr),
                                role=role, 
                                conn_params=conn_params))

    def on_gap_evt_disconnected(self, ble_driver, conn_handle, reason):
        self.event_q.put(_Event('on_gap_evt_disconnected', 
                                conn_handle=conn_handle, 
                                reason=reason))

    def on_gap_evt_sec_params_request(self, ble_driver, conn_handle, peer_params):
        self.event_q.put(_Event('on_gap_evt_sec_params_request', 
                                conn_handle=conn_handle, 
                                peer_params=peer_params))

    def on_gap_evt_conn_param_update_request(self, ble_driver, conn_handle, conn_params):
        self.event_q.put(_Event('on_gap_evt_conn_param_update_request', 
                                conn_handle=conn_handle, 
                                conn_params=conn_params))
        
    def on_gap_evt_timeout(self, ble_driver, conn_handle, src):
        self.event_q.put(_Event('on_gap_evt_timeout', 
                                conn_handle=conn_handle, 
                                src=src))

    def on_gap_evt_adv_report(self, ble_driver, conn_handle, peer_addr, rssi, adv_type, adv_data):
        self.event_q.put(_Event('on_gap_evt_adv_report', 
                                conn_handle=conn_handle, 
                                peer_addr=_SerBLEGapAddr(peer_addr), 
                                rssi=rssi, 
                                adv_type=adv_type, 
                                adv_data=_SerBLEAdvData(adv_data)))

    def on_evt_tx_complete(self, ble_driver, conn_handle, count):
        self.event_q.put(_Event('on_evt_tx_complete', 
                                conn_handle=conn_handle, 
                                count=count))

    def on_gattc_evt_write_rsp(self, ble_driver, conn_handle, status, error_handle, attr_handle, write_op, offset, data):
        self.event_q.put(_Event('on_gattc_evt_write_rsp', 
                                conn_handle=conn_handle, 
                                status=status, 
                                error_handle=error_handle, 
                                attr_handle=attr_handle, 
                                write_op=write_op, 
                                offset=offset, 
                                data=data))

    def on_gattc_evt_hvx(self, ble_driver, conn_handle, status, error_handle, attr_handle, hvx_type, data):
        self.event_q.put(_Event('on_gattc_evt_hvx', 
                                conn_handle=conn_handle, 
                                status=status, 
                                error_handle=error_handle, 
                                attr_handle=attr_handle, 
                                hvx_type=hvx_type, 
                                data=data))
        
    def on_gattc_evt_read_rsp(self, ble_driver, conn_handle, status, error_handle, attr_handle, offset, data):
        self.event_q.put(_Event('on_gattc_evt_read_rsp', 
                                conn_handle=conn_handle, 
                                status=status, 
                                error_handle=error_handle, 
                                attr_handle=attr_handle, 
                                offset=offset, 
                                data=data))

    def on_gattc_evt_prim_srvc_disc_rsp(self, ble_driver, conn_handle, status, services):
        self.event_q.put(_Event('on_gattc_evt_prim_srvc_disc_rsp', 
                                conn_handle=conn_handle, 
                                status=status, 
                                services=services))

    def on_gattc_evt_char_disc_rsp(self, ble_driver, conn_handle, status, characteristics):
        self.event_q.put(_Event('on_gattc_evt_char_disc_rsp', 
                                conn_handle=conn_handle, 
                                status=status, 
                                characteristics=characteristics))

    def on_gattc_evt_desc_disc_rsp(self, ble_driver, conn_handle, status, descriptions):
        self.event_q.put(_Event('on_gattc_evt_desc_disc_rsp', 
                                conn_handle=conn_handle, 
                                status=status, 
                                descriptions=descriptions))

    def on_gap_evt_auth_status(self, ble_driver, conn_handle, auth_status):
        self.event_q.put(_Event('on_gap_evt_auth_status', 
                                conn_handle=conn_handle, 
                                auth_status=auth_status))

    def on_gap_evt_conn_sec_update(self, ble_driver, conn_handle):
        self.event_q.put(_Event('on_gap_evt_conn_sec_update', 
                                conn_handle=conn_handle))

    def on_att_mtu_exchanged(self, ble_driver, conn_handle, att_mtu):
        self.event_q.put(_Event('on_att_mtu_exchanged', 
                                conn_handle=conn_handle, 
                                att_mtu=att_mtu))
        
class BLEDriverMulti(object):
    def __init__(self, serial_port, baud_rate=115200, auto_flash=False):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.auto_flash = auto_flash
        
        self.command_q = multiprocessing.Queue()
        self.response_q = multiprocessing.Queue()
        self.event_q = multiprocessing.Queue()
        self.proc = multiprocessing.Process(target=self._ble_driver)
        self.proc.daemon = True
        self.proc.start()
        self.observers = []
        self.evthandler = threading.Thread(target=self._ble_evt_handler)
        self.evthandler.daemon = True
        self.evthandler.start()
    
    def deserialize_args(self, kwargs):
        if 'peer_addr' in kwargs:
            kwargs['peer_addr'] = kwargs['peer_addr'].deserialize()
        if 'adv_data' in kwargs:
            kwargs['adv_data'] = kwargs['adv_data'].deserialize()
        if 'scan_data' in kwargs:
            kwargs['scan_data'] = kwargs['scan_data'].deserialize()
    
    def _ble_evt_handler(self):
        while True:
            ble_evt = self.event_q.get()
            if ble_evt is None:
                break
            self.deserialize_args(ble_evt.kwargs)
            for obs in self.observers:
                try:
                    func = getattr(obs, ble_evt.name)
                except AttributeError:
                    continue
                try:
                    func(self, **ble_evt.kwargs)
                except Exception as ex:
                    log.error("Exception in observer {} calling {}:\n{}".format(obs, ble_evt.name, traceback.format_exc()))

    def _ble_driver(self):
        ble = BLEDriver(self.serial_port, self.baud_rate, self.auto_flash)
        methods = dict(inspect.getmembers(ble, inspect.ismethod))
        observer = _ObserverMulti(self.event_q)
        ble.observer_register(observer)
        while True:
            cmd = self.command_q.get()
            if cmd is None:
                break
            self.deserialize_args(cmd.kwargs)
            try:
                res = methods[cmd.cmd](*cmd.args, **cmd.kwargs)
            except Exception as ex:
                self.response_q.put(_CommandAck(exception=(ex, traceback.format_exc())))
            else:
                self.response_q.put(_CommandAck(result=res))
            
    def _wait_for_result(self):
        ack = self.response_q.get()
        if ack.exception is not None:
            log.error(ack.exception[1])
            raise ack.exception[0]
        if ack.result is not None:
            return ack.result
    
    def open(self):
        self.command_q.put(_Command('open'))
        return self._wait_for_result()
        
    def close(self):
        self.command_q.put(_Command('close'))
        res = self._wait_for_result()
        self.command_q.put(None)
        self.event_q.put(None)
        self.proc.join()
        self.evthandler.join()
        return res
        
    def observer_register(self, observer):
        self.observers.append(observer)

    def observer_unregister(self, observer):
        self.observers.remove(observer)

    def ble_enable(self, ble_enable_params=None):
        self.command_q.put(_Command('ble_enable', ble_enable_params=ble_enable_params))
        return self._wait_for_result()

    def ble_gap_adv_start(self, adv_params=None):
        self.command_q.put(_Command('ble_gap_adv_start', adv_params=adv_params))
        return self._wait_for_result()

    def ble_gap_conn_param_update(self, conn_handle, conn_params):
        self.command_q.put(_Command('ble_gap_conn_param_update', conn_handle, conn_params))
        return self._wait_for_result()

    def ble_gap_adv_stop(self):
        self.command_q.put(_Command('ble_gap_adv_stop'))
        return self._wait_for_result()

    def ble_gap_scan_start(self, scan_params=None):
        self.command_q.put(_Command('ble_gap_scan_start', scan_params=scan_params))
        return self._wait_for_result()

    def ble_gap_scan_stop(self):
        self.command_q.put(_Command('ble_gap_scan_stop'))
        return self._wait_for_result()

    def ble_gap_connect(self, address, scan_params=None, conn_params=None):
        self.command_q.put(_Command('ble_gap_connect', address, scan_params=scan_params, conn_params=conn_params))
        return self._wait_for_result()

    def ble_gap_disconnect(self, conn_handle, hci_status_code = BLEHci.remote_user_terminated_connection):
        self.command_q.put(_Command('ble_gap_disconnect', conn_handle, hci_status_code=hci_status_code))
        return self._wait_for_result()

    def ble_gap_adv_data_set(self, adv_data=BLEAdvData(), scan_data=BLEAdvData()):
        self.command_q.put(_Command('ble_gap_adv_data_set', adv_data=_SerBLEAdvData(adv_data), scan_data=_SerBLEAdvData(scan_data)))
        return self._wait_for_result()

    def ble_gap_authenticate(self, conn_handle, sec_params):
        self.command_q.put(_Command('ble_gap_authenticate', conn_handle, sec_params))
        return self._wait_for_result()

    def ble_gap_sec_params_reply(self, conn_handle, sec_status, sec_params, own_keys, peer_keys):
        self.command_q.put(_Command('ble_gap_sec_params_reply', conn_handle, sec_status, sec_params, own_keys, peer_keys))
        return self._wait_for_result()
        
    def ble_vs_uuid_add(self, uuid_base):
        self.command_q.put(_Command('ble_vs_uuid_add', uuid_base))
        return self._wait_for_result()

    def ble_gattc_write(self, conn_handle, write_params):
        self.command_q.put(_Command('ble_gattc_write', conn_handle, write_params))
        return self._wait_for_result()

    def ble_gattc_read(self, conn_handle, handle, offset):
        self.command_q.put(_Command('ble_gattc_read', conn_handle, handle, offset))
        return self._wait_for_result()

    def ble_gattc_prim_srvc_disc(self, conn_handle, srvc_uuid, start_handle):
        self.command_q.put(_Command('ble_gattc_prim_srvc_disc', conn_handle, srvc_uuid, start_handle))
        return self._wait_for_result()

    def ble_gattc_char_disc(self, conn_handle, start_handle, end_handle):
        self.command_q.put(_Command('ble_gattc_char_disc', conn_handle, start_handle, end_handle))
        return self._wait_for_result()

    def ble_gattc_desc_disc(self, conn_handle, start_handle, end_handle):
        self.command_q.put(_Command('ble_gattc_desc_disc', conn_handle, start_handle, end_handle))
        return self._wait_for_result()

    def ble_gattc_exchange_mtu_req(self, conn_handle):
        self.command_q.put(_Command('ble_gattc_exchange_mtu_req', conn_handle))
        return self._wait_for_result()
        