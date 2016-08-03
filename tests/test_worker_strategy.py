from frontera.worker.strategy import StrategyWorker
from frontera.worker.strategies.bfs import CrawlingStrategy
from frontera.settings import Settings
from frontera.core.models import Request, Response
from frontera.core.components import States


r1 = Request('http://www.example.com/', meta={'fingerprint': 1, 'jid': 0})
r2 = Request('http://www.scrapy.org/', meta={'fingerprint': 2, 'jid': 0})
r3 = Request('https://www.dmoz.org', meta={'fingerprint': 3, 'jid': 0})
r4 = Request('http://www.test.com/some/page', meta={'fingerprint': 4, 'jid': 0})


class TestStrategyWorker(object):

    def sw_setup(self):
        settings = Settings()
        settings.BACKEND = 'frontera.contrib.backends.sqlalchemy.Distributed'
        settings.MESSAGE_BUS = 'tests.mocks.message_bus.FakeMessageBus'
        settings.SPIDER_LOG_CONSUMER_BATCH_SIZE = 100
        return StrategyWorker(settings, CrawlingStrategy)

    def test_add_seeds(self):
        sw = self.sw_setup()
        msg = sw._encoder.encode_add_seeds([r1, r2, r3, r4])
        sw.consumer.put_messages([msg])
        r2.meta['state'] = States.CRAWLED
        sw.states.update_cache([r2])
        sw.work()
        assert set(sw.scoring_log_producer.messages) == \
            set([sw._encoder.encode_update_score(r.meta['fingerprint'], 1.0, r.url, True)
                for r in [r1, r3, r4]])

    def test_page_crawled(self):
        sw = self.sw_setup()
        r1.meta['jid'] = 1
        resp = Response(r1.url, request=r1)
        msg = sw._encoder.encode_page_crawled(resp, [r2, r3, r4])
        sw.consumer.put_messages([msg])
        sw.work()
        assert sw.scoring_log_producer.messages == []
        sw.job_id = 1
        r2.meta['state'] = States.QUEUED
        sw.states.update_cache([r2])
        sw.consumer.put_messages([msg])
        sw.work()
        assert set(sw.scoring_log_producer.messages) == \
            set(sw._encoder.encode_update_score(r.meta['fingerprint'],
                sw.strategy.get_score(r.url), r.url, True) for r in [r3, r4])

    def test_request_error(self):
        sw = self.sw_setup()
        msg = sw._encoder.encode_request_error(r4, 'error')
        sw.consumer.put_messages([msg])
        sw.work()
        assert sw.scoring_log_producer.messages.pop() == \
            sw._encoder.encode_update_score(r4.meta['fingerprint'], 0.0, r4.url, False)
