# Licensed to Modin Development Team under one or more contributor license agreements.
# See the NOTICE file distributed with this work for additional information regarding
# copyright ownership.  The Modin Development Team licenses this file to you under the
# Apache License, Version 2.0 (the "License"); you may not use this file except in
# compliance with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

import ray
import os
import time
import threading
import warnings

progress_bars = {}
bar_lock = threading.Lock()


def call_progress_bar(result_parts, line_no):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from tqdm.autonotebook import tqdm as tqdm_notebook
        from IPython import get_ipython

    cell_no = get_ipython().execution_count
    pbar_id = str(cell_no) + "-" + str(line_no)
    futures = [x.oid for row in result_parts for x in row]
    bar_format = (
        "{l_bar}{bar}{r_bar}"
        if "DEBUG_PROGRESS_BAR" in os.environ
        and os.environ["DEBUG_PROGRESS_BAR"] == "True"
        else "{desc}: {percentage:3.0f}%{bar} Elapsed time: {elapsed}, estimated remaining time: {remaining}"
    )
    bar_lock.acquire()
    if pbar_id in progress_bars:
        progress_bars[pbar_id].container.children[0].max = progress_bars[
            pbar_id
        ].container.children[0].max + len(futures)
        progress_bars[pbar_id].total = progress_bars[pbar_id].total + len(futures)
        progress_bars[pbar_id].refresh()
    else:
        progress_bars[pbar_id] = tqdm_notebook(
            total=len(futures),
            desc="Estimated completion of line " + str(line_no),
            bar_format=bar_format,
            leave=False,
        )
    bar_lock.release()

    threading.Thread(target=show_time_updates, args=(progress_bars[pbar_id],)).start()
    for i in range(1, len(futures) + 1):
        ray.wait(futures, num_returns=i)
        progress_bars[pbar_id].update(1)
        progress_bars[pbar_id].refresh()
    if progress_bars[pbar_id].n == progress_bars[pbar_id].total:
        progress_bars[pbar_id].close()


def display_time_updates(bar):
    threading.Thread(target=show_time_updates, args=(bar,)).start()


def show_time_updates(p_bar):
    if hasattr(p_bar.container.children[0], "max"):
        index = 0
    else:
        index = 1
    while p_bar.container.children[index].max > p_bar.n:
        time.sleep(1)
        if p_bar.container.children[index].max > p_bar.n:
            p_bar.refresh()
